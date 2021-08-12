#!/usr/bin/env python3
'''
This script allows to launch automatic subtitling on all media from the most recent to the oldest
'''
import time
import os
import sys
import argparse


def do_request(*args, **kwargs):
    global msc
    before = time.time()
    response = msc.api(*args, **kwargs)
    took = time.time() - before
    took_ms = int(took * 1000)
    print(f'Request on {args[0]} took {took_ms} ms')
    return response


def subtitle_all_videos(max_items):
    total = 0
    launched = 0
    has_subs = 0
    cannot_launch = 0

    more = True
    start = ''
    while more:
        print('Making request on latest (start=%s)' % start)
        response = do_request('latest/', params=dict(start=start, content='v', count=20, order_by='creation'))
        for item in response['items']:
            total += 1
            oid = item['oid']
            print(f'Listing subtitles on {oid}')
            subs = do_request(
                'subtitles/',
                method='get',
                params=dict(object_id=oid),
            )['subtitles']
            if not subs:
                r = do_request(
                    'subtitles/generate/',
                    method='post',
                    data=dict(object_id=oid),
                    ignored_status_codes=[400],  # happens if no usable resources are available
                )
                if not r.get('error'):
                    launched += 1
                    print(r['message'])
                else:
                    cannot_launch += 1
                    print(r)
            else:
                has_subs += 1

            if max_items != 0 and total >= max_items:
                print('Reached --max-items, stopping')
                more = None
                break

        start = response['max_date']
        if more is None:
            break
        more = response['more']

    print(f'Launched {launched}/{total}, {has_subs} media already had some subs, {cannot_launch} cannot be launched')


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--conf',
        help='Path to the configuration file.',
        default='config.json',
        type=str
    )

    parser.add_argument(
        '--max-items',
        help='Exit after N media (useful for a small batch test), 0 = never stop',
        default=0,
        type=int
    )

    args = parser.parse_args()
    global msc
    msc = MediaServerClient(args.conf)
    msc.check_server()
    subtitle_all_videos(args.max_items)
