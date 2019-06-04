#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to download all best quality video files from a MediaServer.

To use this script clone MediaServer client, configure it and run this file.
git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/download_all_original_files.py
'''
import os
import re
import subprocess
import sys


def download_all_original_files(msc, dir_path='videos'):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    more = True
    start = ''
    index = 0
    failed = list()
    while more:
        print('//// Making request on latest (start=%s)' % start)
        response = msc.api('latest/', params=dict(start=start, content='v', count=20))
        for item in response['items']:
            index += 1
            print('// Media %s' % index)
            resources = msc.api('medias/resources-list/', params=dict(oid=item['oid']))['resources']
            resources.sort(key=lambda a: -a['file_size'])
            best_quality = None
            for r in resources:
                if r['protocol'] == 'http' and r['format'] not in ('m3u8', 'youtube', 'embed'):
                    best_quality = r
                    break
            video_page = msc.conf['SERVER_URL'] + '/permalink/' + item['oid'] + '/'
            if not best_quality:
                print('WARNING: No resource file found for video "%s"!' % video_page)
            else:
                print('Best quality file for video "%s": %s' % (video_page, best_quality['file']))
                name = re.sub(r'[^A-Za-z0-9]+', '-', item['title'])[:30]
                destination = '%s/%s_%s_%sx%s.%s' % (dir_path, item['oid'], name, best_quality['width'], best_quality['height'], best_quality['format'])
                p = subprocess.run(['wget', '--no-check-certificate', best_quality['file'], '-O', destination])
                if p.returncode != 0:
                    failed.append((item['oid'], best_quality['file'], destination))
        start = response['max_date']
        more = response['more']

    if failed:
        print('Some file download have failed:')
        for f in failed:
            print('%s\t%s\t' % f)
    else:
        print('All download have been done successfully.')


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    dir_path = sys.argv[2] if len(sys.argv) > 2 else ''

    download_all_original_files(msc, dir_path)
