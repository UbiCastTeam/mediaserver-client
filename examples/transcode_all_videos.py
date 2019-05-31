#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to transcode and clean all videos from a MediaServer.

This script requires MediaServer >= 8.2.0.

To use this script clone MediaServer client, configure it and run this file.
git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/transcode_all_videos.py
'''
import json
import os
import sys


DEFAULT_TASKS_PRIORITY = 5


def transcode_all_videos(msc, priority):
    more = True
    start = ''
    index = 0
    succeeded = 0
    failed = 0
    non_transcodable = 0
    while more:
        print('//// Making request on latest (start=%s)' % start)
        response = msc.api('latest/', params=dict(start=start, content='v', count=20))
        for item in response['items']:
            index += 1
            print('// Media %s: %s' % (index, item['oid']))
            try:
                msc.api('medias/task/', method='post', data=dict(
                    oid=item['oid'],
                    task='transcoding',
                    params=json.dumps(dict(priority=priority or DEFAULT_TASKS_PRIORITY, delete_extra_files=True))
                ), timeout=300)
            except Exception as e:
                if 'has no usable ressources' in str(e):
                    non_transcodable += 1
                else:
                    print('WARNING: Failed to start transcoding task of video %s: %s' % (item['oid'], e))
                    failed += 1
            else:
                succeeded += 1
        start = response['max_date']
        more = response['more']

    print('%s transcoding tasks started.' % succeeded)
    print('%s transcoding tasks failed to be started.' % failed)
    print('%s media have no resouces and cannot be transcoded.' % non_transcodable)
    print('Total media count: %s.' % (succeeded + failed + non_transcodable))


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    priority = int(sys.argv[2] if len(sys.argv) > 2 else '0')

    transcode_all_videos(msc, priority)
