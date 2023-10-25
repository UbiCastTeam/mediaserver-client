#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Restore all media from trash described by oids in a CSV file (first column)
'''
import os
import sys
import argparse


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--conf',
        help='Path to the configuration file.',
        required=True,
        type=str
    )

    parser.add_argument(
        '--csv',
        help='Path to CSV file; the first column is expected to be the OID. Lines starting with "#" will be ignored',
        required=True,
        type=str
    )

    parser.add_argument(
        '--csv-separator',
        help='CSV separator',
        default='\t',
        type=str
    )

    parser.add_argument(
        '--apply',
        action='store_true',
        default=False,
        help='Really delete; without this flag, an estimation of the freed space will be printed instead.'
    )

    args = parser.parse_args()

    msc = MediaServerClient(args.conf)

    with open(args.csv, 'r') as f:
        csv_data = f.read().strip()
        lines = [line for line in csv_data.split('\n') if (line and not line.startswith('#'))]
        oids = [line.split(args.csv_separator)[0] for line in lines]
        print(f'About to restore {len(oids)} media')

        if not args.apply:
            print(f'About to restore {len(oids)} media: {oids}')
        else:
            restored_statuses = msc.api('/catalog/bulk_restore/', method='post', data={"oids": oids})["statuses"]

            restored_media_count = 0
            for object_id, status in restored_statuses.items():
                if status["status"] == 200:
                    restored_media_count += 1
                else:
                    print(f"Error: media {object_id} could not be restored: {status.get('message')}")

            print(f'Restored {restored_media_count} media')
