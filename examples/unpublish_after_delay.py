#!/usr/bin/env python3
'''
Script that will automatically unpublish any content N days after it was initially published

This script requires MediaServer >= 8.2.0.
'''
import argparse
import os
import sys
from datetime import datetime


def unpublish_all_videos_after(msc, args):
    delay_days = args.delay_days
    apply = args.apply
    title_filter = args.title_filter

    unpublished = list()
    videos = msc.get_catalog(fmt='flat').get('videos', list())
    videos_count = len(videos)
    for index, item in enumerate(videos):
        oid = item['oid']
        print(f'// Media {index + 1}/{videos_count}: {oid}')

        if title_filter:
            if title_filter not in item['title']:
                print(f"Skipping {oid} because title does not match")
                continue

        publish_date = item.get('publish_date')
        if publish_date and item.get('validated'):
            publish_date_obj = datetime.strptime(publish_date, '%Y-%m-%d %H:%M:%S')
            media_age = (datetime.now() - publish_date_obj).days
            if media_age >= delay_days:
                unpublished.append([oid, media_age])
    for oid, media_age in unpublished:
        if apply:
            print(f'Unpublishing {oid}')
            msc.api('medias/edit/', method='post', data={'validated': 'no', 'oid': oid})
        else:
            print(
                f'[Dry Run] Would unpublish {oid} because it is {media_age} days old (> {delay_days})'
            )
    print(f'Found {len(unpublished)} media to unpublish')


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

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
        '--title-filter',
        type=str,
        help='Only consider media whose title contain this string',
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
    unpublish_all_videos_after(msc, args)
