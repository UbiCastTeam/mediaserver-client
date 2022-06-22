#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to generate a CSV file for metadata from all media in the database
'''
import csv
import os
import sys


def generate_csv(msc, csv_path):
    fields = [
        'oid',
        'title',
        'creation',
        'origin',
        'language',
        'comments'
        'views',
        'views_last_month',
        'speaker_email',
        'location',
        'tree',
        'duration',
        'storage_used',
    ]

    with open(csv_path, 'w') as f:
        more = True
        start = ''
        index = 0

        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t')
        writer.writeheader()

        while more:
            print('//// Making request on latest (start=%s)' % start)
            response = msc.api('latest/', params=dict(start=start, content='v', count=100))
            for item in response['items']:
                index += 1
                print('// Media %s' % index)
                params = {
                    'oid': item['oid'],
                    'path': 'yes',
                }

                data = msc.api('medias/get/', params=params)['info']
                row = {}
                # only copy fields we need
                for field in fields:
                    if data.get(field):
                        row[field] = data[field]
                path = '/'.join([item['title'] for item in data['path']])
                row['tree'] = path
                writer.writerow(row)
            start = response['max_date']
            more = response['more']


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    csv_path = 'media.csv'
    if os.path.isfile(csv_path):
        print(f'File {csv_path} already exists, exiting with error')
        sys.exit(1)

    generate_csv(msc, csv_path)
