#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Delete all media described by oids in a CSV file (first column)

WARNING: THIS CANNOT BE CANCELED BE VERY CAREFUL WITH THIS SCRIPT

By default, does just predict how much space is freed

$ python examples/mass_delete.py --conf ubicast.json --csv media.csv
v12345649684
...
Deleting 7 media would have freed 4.1 GB

To really delete:
$ python examples/mass_delete.py --conf ubicast.json --csv media.csv --apply


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

    parser.add_argument(
        '--apply',
        action='store_true',
        default=False,
        help='Really delete; without this flag, an estimation of the freed space will be printed instead.'
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
        print(f'About to delete {total_lines} media')
        # there is a limit to how many subprocesses can be launched
        if total_lines > 30000:
            print('We recommend against deleting that many files at once')
            sys.exit(1)

        for index, line in enumerate(lines):
            oid = line.split(args.csv_separator)[0]
            if oid:
                params = {'oid': oid, 'full': 'yes'}
                try:
                    print(f'[{index+1}/{total_lines}] About to delete {oid}')
                    info = msc.api('medias/get/', params=params)['info']
                    freed += info['storage_used']
                    if args.apply:
                        data = {
                            'oid': oid,
                            'delete_metadata': 'yes',
                            'delete_resources': 'yes',
                        }
                        print(f'Deleting {oid}')
                        msc.api('medias/delete/', method='post', data=data)
                    count += 1
                except Exception as e:
                    print(f'Error on {oid}: {e}')
        freed_gb = round(freed / GB, 1)
        if not args.apply:
            print(f'Deleting {count} media would have freed {freed_gb} GB ({freed} bytes)')
        else:
            print(f'Deleted {count} media, freed {freed_gb} GB ({freed} bytes)')
