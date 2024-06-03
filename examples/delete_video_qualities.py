#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to delete unwanted video qualities from a channel or using a csv file.
All best mp4 or mp3 files are preserved.
'''

import argparse
import csv
import logging
import os
import re
import sys
import time

try:
    from ms_client.client import MediaServerClient, MediaServerRequestError
except ModuleNotFoundError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient, MediaServerRequestError

DELETED_STATS = {'count': 0, 'size': 0}

logger = logging.getLogger(__name__)


def remove_resources(msc, video_oid, video_title, qualities_to_delete, formats_to_delete, enable_delete=False):
    try:
        _remove_resources(
            msc,
            video_oid,
            video_title,
            qualities_to_delete,
            formats_to_delete,
            enable_delete=enable_delete)
    except Exception as e:
        logger.error(f'Error: {e}, retrying in 30s.')
        time.sleep(30)
        _remove_resources(
            msc,
            video_oid,
            video_title,
            qualities_to_delete,
            formats_to_delete,
            enable_delete=enable_delete)


def _remove_resources(msc, video_oid, video_title, qualities_to_delete, formats_to_delete, enable_delete=False):
    logger.info(f'-- Media {video_oid} "{video_title}"')

    # Update resources from video media
    resources = msc.api('medias/resources-check/', method='post', data=dict(oid=video_oid))

    # Get resources from video media
    resources = msc.api('medias/resources-list/', params=dict(oid=video_oid))['resources']

    # Ignore non managed resources
    resources = [res for res in resources if (
        (res.get('manager') or {}).get('service') in ('local', 'object')
        and res['format'] not in ('embed', 'youtube')
    )]

    if len(resources) <= 1:
        logger.info('The media has only one or zero resource, nothing to delete.')
        return

    # Get reference format depending on media qualities
    ref_format = 'mp3'
    for res in resources:
        if res['height'] > 0:
            ref_format = 'mp4'
            break

    # Sort by format and decreasing quality
    resources.sort(key=lambda a: (
        a['format'] != ref_format,
        a['format'] == 'm3u8',
        '_clean.' in a['path'] or '_original.' in a['path'],
        -a['height'],
        -a['file_size']
    ))

    # Always keep the reference or the best resource but never a m3u8
    ref_res = resources.pop(0)
    logger.info(f'Reference file is "{ref_res["path"]}" and will not be deleted.')
    if ref_res['path'].endswith('.m3u8'):
        logger.info('Warning: The reference is a m3u8 file, media skipped.')
        return

    # Filter resources
    if formats_to_delete:
        filtered_resources = [res for res in resources if res['format'] in formats_to_delete]
    else:
        filtered_resources = resources

    if not filtered_resources:
        logger.info('The media has no matching resources to delete.')
        return

    del_count = 0
    for res in filtered_resources:
        if qualities_to_delete == '*' or res['height'] in qualities_to_delete:
            DELETED_STATS['count'] += 1
            DELETED_STATS['size'] += res['file_size']
            if enable_delete:
                try:
                    msc.api(
                        'medias/resources-delete/',
                        method='post',
                        data=dict(oid=video_oid, names=res['path']),
                        timeout=180
                    )
                    del_count += 1
                except MediaServerRequestError as err:
                    if 'read timeout=' in str(err):
                        logger.warning(
                            f'The deletion request timed out for "{res["path"]}" from media "{video_title}",'
                            ' this error can be ignored.')
                    else:
                        logger.error(f'Failed to delete resource "{res["path"]}": {str(err).strip()}')
                else:
                    logger.info(f'Resource "{res["path"]}" from media "{video_title}" has been deleted successully.')
            else:
                logger.info(f'[Dry Run] Resource "{res["path"]}" from media "{video_title}" would be deleted.')
                del_count += 1
    if not del_count:
        logger.info('Nothing to delete in this media.')


def process_channel(msc, qualities_to_delete, formats_to_delete, channel_info, enable_delete=False):
    # Browse channels from channel parent
    logger.info(f'Getting content of channel {channel_info["oid"]} "{channel_info["title"]}".')
    channel_items = msc.api(
        'channels/content/',
        method='get',
        params=dict(parent_oid=channel_info['oid'], content='cv')
    )

    # Check sub channels
    for entry in channel_items.get('channels', []):
        process_channel(msc, qualities_to_delete, formats_to_delete, entry, enable_delete=enable_delete)

    logger.info(f'// Checking videos in channel {channel_info["oid"]} "{channel_info["title"]}".')
    # Get video informations
    for entry in channel_items.get('videos', []):
        remove_resources(msc, entry['oid'], entry['title'], qualities_to_delete, formats_to_delete, enable_delete)


def process_csv_file(msc, qualities_to_delete, formats_to_delete, csv_file, enable_delete=False):
    with open(csv_file, 'r') as csvfile:
        csvreader = csv.reader(csvfile, skipinitialspace=True)

        # Skip header
        next(csvreader)

        for row in csvreader:
            # First column must be the oid
            video_oid = row[0]

            try:
                # Get media title and check it exists
                video_title = msc.api('medias/get/', params=dict(oid=video_oid))['info']['title']
            except MediaServerRequestError as err:
                logger.info(f'-- Media {video_oid} ignored:')
                logger.info(f'Failed to get title of media: {str(err).strip()}')
            else:
                remove_resources(msc, video_oid, video_title, qualities_to_delete, formats_to_delete, enable_delete)


def check_resources(msc, qualities_to_delete, formats_to_delete, channel_oid, csv_file, enable_delete=False):
    if csv_file:
        # Check if csv file exists
        if not os.path.exists(csv_file):
            logger.info('Invalid path for csv file.')
            return 1
        process_csv_file(msc, qualities_to_delete, formats_to_delete, csv_file, enable_delete=enable_delete)
        return 0
    elif channel_oid:
        # Check if channel oid exists
        try:
            channel_parent = msc.api('channels/get/', method='get', params=dict(oid=channel_oid))
        except MediaServerRequestError as err:
            logger.info('Please enter a valid channel oid or check access permissions.')
            logger.info(f'Error when trying to get channel was: {str(err).strip()}')
            return 1
        logger.info(f'Parent Channel is "{channel_parent["info"]["title"]}".')
        process_channel(
            msc,
            qualities_to_delete,
            formats_to_delete,
            channel_parent['info'],
            enable_delete=enable_delete)
        return 0
    else:
        # Process all channels
        info = {'oid': '', 'title': 'root'}
        logger.info(f'Parent Channel is "{info["title"]}".')
        process_channel(
            msc,
            qualities_to_delete,
            formats_to_delete,
            info,
            enable_delete=enable_delete)
        return 0


def qualities_type(value):
    if value == '*':
        return value
    if not re.match(r'(\d+,?)+', value):
        raise ValueError('Invalid format for "qualities", expected format is "height1,height2", for example "360,720".')
    qualities = [int(v) for v in value.strip(',').split(',')]
    return qualities


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.strip())
    group = parser.add_mutually_exclusive_group()

    parser.add_argument(
        '--conf',
        dest='configuration',
        help='Path to the configuration file.',
        required=True,
        type=str)

    parser.add_argument(
        '--qualities',
        dest='qualities',
        help='Qualities to delete. Format is "height1,height2", for example "360,720". '
             'Use "0" to target audio files. Use "*" to delete all qualities. '
             'The reference mp4 or mp3 file is never deleted.',
        required=True,
        type=qualities_type)

    parser.add_argument(
        '--formats',
        dest='formats',
        help='File extensions to delete. Format is for example "mp4,aspx". '
             'If no value is specified, all formats will be targetted. '
             'The reference mp4 or mp3 file is never deleted.',
        default='',
        type=str)

    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        dest='enable_delete',
        help='Enable files deletion. If not enabled, the script will be run in dry run mode.')

    group.add_argument(
        '--channel',
        dest='channel_oid',
        help='Channel oid to check. If no channel and no CSV is given, all channels will be checked.',
        type=str)

    group.add_argument(
        '--csv',
        dest='csv_file',
        help='CSV file with a list of videos oids. If no channel and no CSV is given, all channels will be checked.',
        type=str)

    args = parser.parse_args()

    print(f'Configuration path: {args.configuration}')
    print(f'Qualities to delete: {args.qualities}')
    print(f'Enable delete: {args.enable_delete}')
    print(f'Parent channel oid: {args.channel_oid}')
    print(f'CSV file: {args.csv_file}')

    # Check if configuration file exists
    if not args.configuration.startswith('unix:') and not os.path.exists(args.configuration):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration)
    msc.check_server()
    # Increase default timeout because deletions can be very disk intensive and slow the server
    msc.conf['TIMEOUT'] = max(60, msc.conf['TIMEOUT'])

    rc = check_resources(
        msc,
        args.qualities,
        args.formats.split(',') if args.formats else None,
        args.channel_oid,
        args.csv_file,
        args.enable_delete)

    deleted_size_gb = int(DELETED_STATS['size'] / 1_000_000_000)
    if args.enable_delete:
        logger.info(
            f'Deleted {deleted_size_gb} GB ({DELETED_STATS["count"]} resources).')
    else:
        logger.info(
            f'Would have freed {deleted_size_gb} GB ({DELETED_STATS["count"]} resources) if run with "--delete".')

    sys.exit(rc)
