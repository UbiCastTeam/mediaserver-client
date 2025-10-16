#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
This script will go over all channels and apply a different sorting to a specific value
'''
import argparse
import os
import sys


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument(
        "--conf",
        help="Path to the configuration file (e.g. myconfig.json).",
        required=True,
        type=str,
    )

    SORTINGS = [
        "creation_date-desc",
        "creation_date-asc",
        "add_date-desc",
        "add_date-asc",
        "title-desc",
        "title-asc",
        "comments-desc",
        "comments-asc",
        "views-desc",
        "views-asc",
    ]
    parser.add_argument(
        "--sorting",
        help="Type of sorting to apply to target channels",
        choices=SORTINGS,
        required=True,
    )

    args = parser.parse_args()
    msc = MediaServerClient(args.conf)
    # ping
    print('Fetching catalog')
    all_channels = msc.get_catalog(fmt='flat').get('channels')
    channels_count = len(all_channels)
    for index, channel in enumerate(all_channels):
        oid = channel['oid']
        print(f'Applying sorting on channel {oid} {index + 1}/{channels_count}')
        msc.api('/channels/edit/', method='post', data={'oid': oid, 'sorting': args.sorting})
