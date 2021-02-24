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


def find_duplicate(msc, channel_parent_oid, enable_delete=False):

    videos_reference = dict()
    ms_url = msc.conf['SERVER_URL'] + '/permalink/'

    # Check if parent channel oid exists
    try:
        channel_parent = msc.api('channels/get/', method='get', params=dict(oid=channel_parent_oid))
    except Exception:
        print('Please enter valid channel oid.')
        return 1

    print('Parent Channel is %s' % channel_parent['info']['title'])

    channel_tree = msc.api('/channels/tree/', method='get', params=dict(parent_oid=channel_parent_oid, recursive='yes'))['channels']

    # Browse channels from channel parent
    for channel in channel_tree:
        print('Check videos in channel %s' % (channel['title']))
        videos_oid = msc.api('channels/content/', method='get', params=dict(parent_oid=channel['oid'], content='v'))

        # Check if there are videos in the channel otherwise skip
        if(len(videos_oid.keys()) == 1):
            continue

        # Get video informations
        for video_oid in videos_oid['videos']:
            video_info = msc.api('medias/get/', method='get', params=dict(oid=video_oid['oid']))['info']
            date_creation = re.search(r'\d{4}-\d{2}-\d{2}', video_info['creation'])

            video_title = video_info['title']
            video_oid = video_info['oid']
            video_duration = video_info['duration']
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
    return 0


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--conf',
        dest='configuration_path',
        help='Path to the configuration file.',
        required=True,
        type=str)

    parser.add_argument(
        '--channel_parent',
        dest='channel_parent_oid',
        help='Channel Parent oid to check',
        required=True,
        type=str)

    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        dest='enable_delete',
        help='Delete media in MediaServer.')

    args = parser.parse_args()

    print('Configuration path: %s' % args.configuration_path)
    print('Parent channel oid: %s' % args.channel_parent_oid)
    print('Enable delete: %s' % args.enable_delete)

    # Check if configuration file exists
    if not args.configuration_path.startswith('unix:') and not os.path.exists(args.configuration_path):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration_path)
    msc.check_server()

    rc = find_duplicate(msc, args.channel_parent_oid, args.enable_delete)
    sys.exit(rc)
