#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to detect and remove duplicate videos on MediaServer.
'''

import argparse
import os
import re
import sys


def get_key_from_value_dict(videos_reference, search_value, search_field):
    void_list = list()
    for key, value in videos_reference.items():
        if search_value in value[search_field]:
            void_list.append(key)
    return void_list


def process_channel(msc, channel_info, enable_delete=False, videos_reference=None):
    if videos_reference is None:
        videos_reference = dict()
    ms_url = msc.conf['SERVER_URL'] + '/permalink/'

    # Browse channels from channel parent
    print('Check videos in channel %s %s' % (channel_info['oid'], channel_info['title']))
    channel_items = msc.api('channels/content/', method='get', params=dict(parent_oid=channel_info['oid'], content='cv'))

    # Check sub channels
    for entry in channel_items.get('channels', []):
        process_channel(msc, entry, enable_delete=enable_delete, videos_reference=videos_reference)

    # Get video informations
    for entry in channel_items.get('videos', []):
        date_creation = re.search(r'\d{4}-\d{2}-\d{2}', entry['creation'])

        video_title = entry['title']
        video_oid = entry['oid']
        video_duration = entry['duration']
        video_creation = date_creation.group()

        # Get key (video oid) from video title
        list_oids = get_key_from_value_dict(videos_reference, video_title, 'title')

        # Add video to videos reference as it does not exist
        if not list_oids:
            videos_reference[video_oid] = {'title': video_title, 'duration': video_duration, 'creation': video_creation}
            continue
        for list_oid in list_oids:
            if videos_reference[list_oid]['title'] == video_title:
                if videos_reference[list_oid]['duration'] == video_duration and videos_reference[list_oid]['creation'] == video_creation:
                    print('Video  %s is duplicate of %s' % (ms_url + video_oid, ms_url + list_oid))
                    if enable_delete:
                        try:
                            # msc.api('medias/delete/', method='post', data=dict(oid=video_oid, delete_metadata='yes', delete_resources='yes'))
                            msc.api('medias/edit/', method='post', data=dict(oid=video_oid, description='Duplicate of ' + ms_url + list_oid))
                        except Exception as e:
                            print('Failed to delete media %s: %s' % (video_title, e))
                        else:
                            print('Media %s has been deleted successfully from MediaServer.' % video_title)
                else:
                    # Add video with same title but different duration or creation date
                    videos_reference[video_oid] = {'title': video_title, 'duration': video_duration, 'creation': video_creation}


def find_duplicate(msc, channel_oid, enable_delete=False):
    # Check if channel oid exists
    try:
        channel_parent = msc.api('channels/get/', method='get', params=dict(oid=channel_oid))
    except Exception as e:
        print('Please enter valid channel oid or check access permissions. Error when trying to get channel was: %s' % e)
        return 1
    print('Parent Channel is %s' % channel_parent['info']['title'])
    process_channel(msc, channel_parent['info'], enable_delete=enable_delete)
    return 0


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--conf',
        dest='configuration',
        help='Path to the configuration file.',
        required=True,
        type=str)

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
    print('Parent channel oid: %s' % args.channel_oid)
    print('Enable delete: %s' % args.enable_delete)

    # Check if configuration file exists
    if not args.configuration.startswith('unix:') and not os.path.exists(args.configuration):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration)
    msc.check_server()

    rc = find_duplicate(msc, args.channel_oid, args.enable_delete)
    sys.exit(rc)
