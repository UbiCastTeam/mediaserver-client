#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Put all media described by oids in a CSV file (first column) as public

'''
import os
import sys
import argparse

GB = 1000 * 1000 * 1000


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

    args = parser.parse_args()

    msc = MediaServerClient(args.conf)
    # ping
    print(msc.api('/'))

    with open(args.csv, 'r') as f:
        csv_data = f.read().strip()
        count = 0
        freed = 0
        lines = [line for line in csv_data.split('\n') if (line and not line.startswith('#'))]
        total_lines = len(lines)
        print(f'About to make {total_lines} media public')
        # there is a limit to how many subprocesses can be launched

        for index, line in enumerate(lines):
            oid = line.split(args.csv_separator)[0]
            if oid:
                params = {'oid': oid, 'full': 'yes'}
                try:
                    print(f'[{index+1}/{total_lines}] About to set {oid} public')
                    data = {
                        'oid': oid,
                        'users-anonymous-can_access_media': 'True',
                        'users-authenticated-can_access_media': 'True',
                        'prefix': 'reference',
                    }
                    print(f'Making {oid} public')
                    msc.api('perms/edit/default/', method='post', data=data)
                    count += 1
                except Exception as e:
                    print(f'Error on {oid}: {e}')
        print(f'Made {count} media public')
