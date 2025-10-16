#!/usr/bin/env python3
'''
Script which will produce stats about the video files on the platform
'''
import os
import sys


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient
    from ms_client.lib.utils import format_bytes, format_time

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    print('Dumping catalog')
    videos = msc.get_catalog(fmt='json')['videos']

    all_resources_duration = dict()
    all_resources_count = dict()
    all_resources_size = dict()

    for index, video in enumerate(videos):
        print(f'{index + 1}/{len(videos)}', end='\r')
        oid = video['oid']
        duration = int(video['duration_s'])  # in seconds
        storage = int(video['storage_used'])  # in bytes
        resources = msc.api('/medias/resources-list/', params={'oid': oid})["resources"]
        resources_sorted = sorted(resources, key=lambda d: d["height"], reverse=True)
        if len(resources_sorted) > 0 and duration:
            source_resolution = resources_sorted[0]['height']  # first one should be the largest
            all_resources_duration.setdefault(source_resolution, 0)
            all_resources_duration[source_resolution] += duration
            all_resources_count.setdefault(source_resolution, 0)
            all_resources_count[source_resolution] += 1
            all_resources_size.setdefault(source_resolution, 0)
            all_resources_size[source_resolution] += storage

    print()
    print('Source resolutions by duration:')
    all_resources_duration = dict(
        sorted(all_resources_duration.items(), key=lambda item: item[1], reverse=True)
    )
    for mode, duration in all_resources_duration.items():
        mode_size = all_resources_size[mode]
        size_per_hour = int(mode_size / (duration / 3600))
        print(f'{mode}: {format_time(duration)}, average size: {format_bytes(size_per_hour)} per hour')

    print()
    print('Source resolutions by count:')
    all_resources_count = dict(
        sorted(all_resources_count.items(), key=lambda item: item[1], reverse=True)
    )
    for mode, count in all_resources_count.items():
        print(f'{mode}: {count}')

    print()
    print('Source resolutions by size:')
    all_resources_size = dict(
        sorted(all_resources_size.items(), key=lambda item: item[1], reverse=True)
    )
    for mode, size in all_resources_size.items():
        print(f'{mode}: {format_bytes(size)}')
