#!/usr/bin/env python3
'''
Script which will produce stats about the video files on the platform
'''
import os
import sys


def format_seconds(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    timecode = '%d:%02d:%02d' % (h, m, s)
    return timecode


def format_bytes(size):
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'kilo', 2: 'mega', 3: 'giga', 4: 'tera'}
    while size > power:
        size /= power
        n += 1
    return f'{round(size, 1)} {power_labels[n]}bytes'


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    print('Dumping catalog')
    videos = msc.get_catalog(fmt='json')['videos']

    all_modes_duration = dict()
    all_modes_count = dict()
    all_modes_size = dict()

    for index, video in enumerate(videos):
        print(f'{index + 1}/{len(videos)}', end='\r')
        oid = video['oid']
        duration = int(video['duration_s'])  # in seconds
        storage = int(video['storage_used'])  # in bytes
        modes = msc.api('/medias/modes/', params={'oid': oid, 'all': ''})
        if len(modes['names']) and duration:
            largest_mode = modes['names'][0]
            all_modes_duration.setdefault(largest_mode, 0)
            all_modes_duration[largest_mode] += duration
            all_modes_count.setdefault(largest_mode, 0)
            all_modes_count[largest_mode] += 1
            all_modes_size.setdefault(largest_mode, 0)
            all_modes_size[largest_mode] += storage

    print()
    print('Source resolutions by duration :')
    all_modes_duration = dict(
        sorted(all_modes_duration.items(), key=lambda item: item[1], reverse=True)
    )
    for mode, duration in all_modes_duration.items():
        mode_size = all_modes_size[mode]
        size_per_hour = int(mode_size / (duration / 3600))
        print(f'{mode}: {format_seconds(duration)}, average size: {format_bytes(size_per_hour)} per hour')

    print()
    print('Source resolutions by count :')
    all_modes_count = dict(
        sorted(all_modes_count.items(), key=lambda item: item[1], reverse=True)
    )
    for mode, count in all_modes_count.items():
        print(f'{mode}: {count}')

    print()
    print('Source resolutions by size :')
    all_modes_size = dict(
        sorted(all_modes_size.items(), key=lambda item: item[1], reverse=True)
    )
    for mode, size in all_modes_size.items():
        print(f'{mode}: {format_bytes(size)}')
