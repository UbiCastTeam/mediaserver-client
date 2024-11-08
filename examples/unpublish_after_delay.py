#!/usr/bin/env python3
'''
Script to transcode and clean all videos from a MediaServer.

This script requires MediaServer >= 8.2.0.
'''
import argparse
import os
import sys
from datetime import datetime


def unpublish_all_videos_after(msc, delay_days, apply):
    unpublished = list()
    videos = msc.get_catalog(fmt='flat').get('videos', list())
    videos_count = len(videos)
    for index, item in enumerate(videos):
        oid = item['oid']
        print(f'// Media {index + 1}/{videos_count}: {oid}')
        publish_date = item.get('publish_date')
        if publish_date and item.get('validated'):
            publish_date_obj = datetime.strptime(publish_date, '%Y-%m-%d %H:%M:%S')
            media_age = (datetime.now() - publish_date_obj).days
            if media_age >= delay_days:
                unpublished.append([oid, media_age])
    print(f'Found {len(unpublished)} to unpublish {unpublished}')
    for oid, media_age in unpublished:
        if apply:
            print(f'Unpublishing {oid}')
            msc.api('medias/edit/', method='post', data={'validated': 'no', 'oid': oid})
        else:
            print(
                f'[Dry Run] Would unpublish {oid} because it is {media_age} days old (> {delay_days})'
            )


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--conf', help='Path to the configuration file.', required=True, type=str
    )

    parser.add_argument(
        '--delay-days',
        required=True,
        type=int,
        help='Delay in days after the publish date that media should be unpublished',
    )

    parser.add_argument(
        '--apply',
        action='store_true',
        default=False,
        help='Run in simulation mode unless enabled',
    )

    args = parser.parse_args()
    msc = MediaServerClient(args.conf)
    msc.check_server()
    unpublish_all_videos_after(msc, args.delay_days, args.apply)
