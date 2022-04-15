#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to delete unwanted video qualities from a channel or using a csv file.
All best mp4 or mp3 files are preserved.
'''

import argparse
import csv
import os
import re
import sys


def remove_ressources(msc, video_oid, video_title, qualities_to_delete, enable_delete=False):
    print('-- Media %s "%s"' % (video_oid, video_title))

    # Get resources from video media
    resources = msc.api('medias/resources-list/', params=dict(oid=video_oid))['resources']

    # Get reference format depending on media qualities
    ref_format = 'mp3'
    for res in resources:
        if res['height'] > 0:
            ref_format = 'mp4'
            break

    # Sort by decreasing quality and is mp4
    resources.sort(key=lambda a: (-a['height'], a['format'] != ref_format))

    # Remove mp4 with highest resolution from resource resolutions to delete
    if resources[0]['format'] == ref_format:
        ref_res = resources.pop(0)
        print('Reference file is: %s' % ref_res['path'])

    res_count = len(resources)
    for resources_item in resources:
        # Skip original and cleaned resources
        if '_clean' in resources_item['path'] or '_original' in resources_item['path']:
            continue
        if qualities_to_delete == '*' or resources_item['height'] in qualities_to_delete:
            if enable_delete:
                try:
                    msc.api('medias/resources-delete/', method='post', data=dict(oid=video_oid, names=resources_item['path']))
                    res_count -= 1
                except Exception as e:
                    print('Failed to delete resource "%s": %s' % (resources_item['path'], e))
                else:
                    print('Resource "%s" from media %s has been deleted successully.' % (resources_item['path'], video_title))
            else:
                print('[Dry Run] Resource "%s" from media %s would be deleted.' % (resources_item['path'], video_title))
                res_count -= 1

            # Do not delete last resource
            if res_count == 1:
                break
    if res_count == len(resources):
        print('Nothing to delete in this media.')


def process_channel(msc, qualities_to_delete, channel_info, enable_delete=False):
    # Browse channels from channel parent
    print('Getting content of channel %s "%s".' % (channel_info['oid'], channel_info['title']))
    channel_items = msc.api('channels/content/', method='get', params=dict(parent_oid=channel_info['oid'], content='cv'))

    # Check sub channels
    for entry in channel_items.get('channels', []):
        process_channel(msc, qualities_to_delete, entry, enable_delete=enable_delete)

    print('// Checking videos in channel %s "%s".' % (channel_info['oid'], channel_info['title']))
    # Get video informations
    for entry in channel_items.get('videos', []):
        remove_ressources(msc, entry['oid'], entry['title'], qualities_to_delete, enable_delete)


def process_csv_file(msc, qualities_to_delete, csv_file, enable_delete=False):
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
            except Exception as e:
                print('-- Media %s ignored:' % video_oid)
                print('Failed to get title of media: %s' % str(e).strip())
            else:
                remove_ressources(msc, video_oid, video_title, qualities_to_delete, enable_delete)


def check_ressources(msc, qualities_to_delete, channel_oid, csv_file, enable_delete=False):
    if csv_file:
        # Check if csv file exists
        if not os.path.exists(csv_file):
            print('Invalid path for csv file.')
            return 1
        process_csv_file(msc, qualities_to_delete, csv_file, enable_delete=enable_delete)
        return 0
    else:
        # Check if channel oid exists
        try:
            channel_parent = msc.api('channels/get/', method='get', params=dict(oid=channel_oid))
        except Exception as e:
            print('Please enter a valid channel oid or check access permissions.')
            print('Error when trying to get channel was: %s' % e)
            return 1
        print('Parent Channel is "%s".' % channel_parent['info']['title'])
        process_channel(msc, qualities_to_delete, channel_parent['info'], enable_delete=enable_delete)
        return 0


def qualities_type(value):
    if value == '*':
        return value
    if not re.match(r'(\d+,?)+', value):
        raise ValueError('Invalid format for "qualities", expected format is "height1,height2", for example "360,720".')
    qualities = [int(v) for v in value.strip(',').split(',')]
    return qualities


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

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
        help='Qualities to delete. Format is "height1,height2", for example "360,720". Use "0" to target audio files. Use "*" to delete all qualities. The reference mp4 or mp3 file is never deleted.',
        required=True,
        type=qualities_type)

    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        dest='enable_delete',
        help='Delete media in MediaServer.')

    group.add_argument(
        '--channel',
        dest='channel_oid',
        help='Channel oid to check.',
        type=str)

    group.add_argument(
        '--csv',
        dest='csv_file',
        help='CSV file with oid videos',
        type=str)

    args = parser.parse_args()

    print('Configuration path: %s' % args.configuration)
    print('Qualities to delete: %s' % args.qualities)
    print('Enable delete: %s' % args.enable_delete)
    print('Parent channel oid: %s' % args.channel_oid)
    print('CSV file: %s' % args.csv_file)

    # Check if configuration file exists
    if not args.configuration.startswith('unix:') and not os.path.exists(args.configuration):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration)
    msc.check_server()
    # Increase default timeout because deletions can be very disk intensive and slow the server
    msc.conf['TIMEOUT'] = max(60, msc.conf['TIMEOUT'])

    rc = check_ressources(msc, args.qualities, args.channel_oid, args.csv_file, args.enable_delete)
    sys.exit(rc)
