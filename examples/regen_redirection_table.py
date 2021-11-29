#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to browse all videos and if external_ref is present, add it to a redirection CSV file:
external_ref, oid
'''
import os
import sys


def transcode_all_videos(msc):
    more = True
    start = ''
    redir_count = 0
    index = 0
    with open('redirections.csv', 'w') as f:
        while more:
            print('//// Making request on latest (start=%s)' % start)
            response = msc.api('latest/', params=dict(start=start, content='v', count=20))
            for item in response['items']:
                oid = item['oid']
                index += 1
                data = msc.api(
                    'medias/get/',
                    method='get',
                    params={
                        'oid': oid,
                        'full': 'yes',
                    },
                    timeout=300
                )['info']
                if data.get('external_ref'):
                    line = f'{data["external_ref"]},{oid}'
                    print(line)
                    f.write(line + '\n')
                    redir_count += 1

            start = response['max_date']
            more = response['more']

    print(f'Wrote {redir_count} redirections')


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    transcode_all_videos(msc)
