#!/usr/bin/env python3
'''
Script to dump all info into a json file for easy migrations
'''

import argparse
import os
import sys
import json


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument(
        '--conf',
        help='Path to the configuration file for the source platform.',
        required=True,
        type=str,
    )

    parser.add_argument(
        '--json-path',
        help='Output JSON file path.',
        default='dump.json',
        type=str,
    )

    args = parser.parse_args()

    msc = MediaServerClient(args.conf)
    items = msc.get_catalog(fmt='flat')
    channels = items.get('channels', list())
    channels_dict = dict()
    for c in channels:
        oid = c['oid']
        channels_dict[oid] = c

    channels_paths = dict()
    for oid, channel in channels_dict.items():
        path = [channel['title']]
        parent_oid = channel.get('parent_oid')
        while parent_oid:
            parent_channel = channels_dict[parent_oid]
            parent_title = parent_channel.get('title')
            if parent_title:
                path.append(parent_title)
            parent_oid = parent_channel.get('parent_oid')
        path.reverse()
        channels_paths[oid] = "/".join(path)

    videos = items.get('videos', list())
    print(f'Got {len(videos)} videos, getting download urls')

    for index, v in enumerate(videos):
        print(f"[{index + 1}/{len(videos)}]", end="\r")
        v['download_url'] = msc.get_best_download_url(v["oid"])
        v['path'] = channels_paths[v['parent_oid']]

    print(f'Dumping data to {args.json_path}')
    with open(args.json_path, "w") as f:
        json.dump(videos, f, indent=4, ensure_ascii=False)
