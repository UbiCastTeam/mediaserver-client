#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to generate a CSV file for metadata from all media in the database
'''
import csv
import os
import sys


def parse_duration(dur):
    #'1 h 51 m 21 s'
    fields = dur.split(' ')
    hours_index = minutes_index = seconds_index = None
    if len(fields) == 6:
        hours_index = 0
        minutes_index = 2
        seconds_index = 4
    elif len(fields) == 4:
        minutes_index = 0
        seconds_index = 2
    elif len(fields) == 2:
        seconds_index = 0

    hours = int(fields[hours_index]) if hours_index is not None else 0
    minutes = int(fields[minutes_index]) if minutes_index is not None else 0
    seconds = int(fields[seconds_index]) if seconds_index is not None else 0

    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds


def generate_csv(msc, csv_path):
    fields = [
        'oid',
        'title',
        'duration',
        'storage_used',
        'tree',
        'categories',
        'language',
        'speaker_email',
        'creation',
        'location',
        'validated',
        'type',
        'layout',
        'origin',
        'comments',
        'views',
        'views_last_month',
    ]

    with open(csv_path, 'w') as f:
        more = True
        start = ''
        index = 0

        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t')
        writer.writeheader()

        while more:
            print(f'//// Making request on latest (start={start})')
            response = msc.api('latest/', params=dict(start=start, content='v', count=100))
            for item in response['items']:
                index += 1
                print(f'// Media {index}: {item["oid"]}')

                params = {
                    'oid': item['oid'],
                    'path': 'yes',
                    'full': 'yes',
                }
                data = msc.api('medias/get/', params=params)['info']
                row = {}
                # only copy fields we want
                for field in fields:
                    if data.get(field):
                        if field == 'duration':
                            row[field] = parse_duration(data[field])
                        else:
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

    csv_path = f'media-{msc.conf["SERVER_URL"].split("://")[1]}.csv'
    if os.path.isfile(csv_path):
        print(f'File {csv_path} already exists, exiting with error')
        sys.exit(1)

    generate_csv(msc, csv_path)
    print(f'Finished writing {csv_path}')
