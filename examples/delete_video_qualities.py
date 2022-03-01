#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to delete unwanted video qualities from a channel of MediaServer.
All best mp4 files are preserved.
'''

import argparse
import os
import re
import sys


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
        print('-- Media %s "%s"' % (entry['oid'], entry['title']))

        # Get resources from video media
        resources = msc.api('medias/resources-list/', params=dict(oid=entry['oid']))['resources']

        # Ignore audio files
        resources = [res for res in resources if res['height'] > 0]
        if not resources:
            print('Audio only media, ignoring it.')
            continue

        # Sort by decreasing quality and is mp4
        resources.sort(key=lambda a: (-a['height'], a['format'] != 'mp4'))

        # Remove mp4 with highest resolution from resource resolutions to delete
        if resources[0]['format'] == 'mp4':
            resources.pop(0)

        res_count = len(resources)
        for resources_item in resources:
            # Skip original and cleaned resources
            if '_clean' in resources_item['path'] or '_original' in resources_item['path']:
                continue
            if resources_item['height'] in qualities_to_delete:
                if enable_delete:
                    try:
                        msc.api('medias/resources-delete/', method='post', data=dict(oid=entry['oid'], names=resources_item['path']))
                        res_count -= 1
                    except Exception as e:
                        print('Failed to delete resource "%s": %s' % (resources_item['path'], e))
                    else:
                        print('Resource "%s" from media %s has been deleted successully.' % (resources_item['path'], entry['title']))
                else:
                    print('[Dry Run] Resource "%s" from media %s would be deleted.' % (resources_item['path'], entry['title']))
                    res_count -= 1

                # Do not delete last resource
                if res_count == 1:
                    break
        if res_count == len(resources):
            print('Nothing to delete in this media.')


def check_ressources(msc, qualities_to_delete, channel_oid, enable_delete=False):
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
    if not re.match(r'(\d+,?)+', value):
        raise ValueError('Invalid format for "qualities", expected format is "height1,height2", for example "360,720".')
    qualities = [int(v) for v in value.strip(',').split(',')]
    return qualities


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument(
        '--conf',
        dest='configuration',
        help='Path to the configuration file.',
        required=True,
        type=str)

    parser.add_argument(
        '--qualities',
        dest='qualities',
        help='Qualities to delete. Format is "height1,height2", for example "360,720".',
        required=True,
        type=qualities_type)

    parser.add_argument(
        '--channel',
        dest='channel_oid',
        help='Channel oid to check.',
        required=True,
        type=str)

    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        dest='enable_delete',
        help='Delete media in MediaServer.')

    args = parser.parse_args()

    print('Configuration path: %s' % args.configuration)
    print('Qualities to delete: %s' % args.qualities)
    print('Parent channel oid: %s' % args.channel_oid)
    print('Enable delete: %s' % args.enable_delete)

    # Check if configuration file exists
    if not args.configuration.startswith('unix:') and not os.path.exists(args.configuration):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration)
    msc.check_server()

    rc = check_ressources(msc, args.qualities, args.channel_oid, args.enable_delete)
    sys.exit(rc)
