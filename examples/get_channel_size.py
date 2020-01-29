#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to get the size used by all resources of media in a given channel or in whole catalog if no channel is specified.
The API key used to run this script must have the permission to access resources tab and all media.

To use this script clone MediaServer client and put this file in a sub dir in the client dir.
git clone https://github.com/UbiCastTeam/mediaserver-client
mkdir examples
mv "this file" mediaserver-client/examples
'''
import os
import sys


def get_channel_size(msc, oid, info=None):
    if info is None:
        info = dict(size=0, channels=0, videos=0, lives=0, pgroups=0)
    print('//// Channel %s' % oid)
    print('Making request on channels/content/ (parent_oid=%s)' % oid)
    response = msc.api('channels/content/', params=dict(parent_oid=oid, content='cvlp'))
    if response.get('channels'):
        for item in response['channels']:
            info['channels'] += 1
            get_channel_size(msc, item['oid'], info)
    if response.get('live_streams'):
        for item in response['live_streams']:
            info['lives'] += 1
    if response.get('photos_groups'):
        for item in response['photos_groups']:
            info['pgroups'] += 1
    if response.get('videos'):
        for item in response['videos']:
            print('// Media %s' % item['oid'])
            info['videos'] += 1
            size = 0
            for r in msc.api('medias/resources-list/', params=dict(oid=item['oid']))['resources']:
                size += r['file_size']
            print('Media size: %s' % size)
            info['size'] += size
    return info


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    channel_oid = sys.argv[2] if len(sys.argv) > 2 else ''

    info = get_channel_size(msc, channel_oid)
    print('')
    print('Channel info:')
    print('  - Total resources size: %.2f GB (attachments and slides not included)' % (info['size'] / (1000 ** 3)))
    print('  - Number of videos: %s' % info['videos'])
    print('  - Number of lives: %s' % info['lives'])
    print('  - Number of photos groups: %s' % info['pgroups'])
    print('  - Number of channels: %s' % info['channels'])
