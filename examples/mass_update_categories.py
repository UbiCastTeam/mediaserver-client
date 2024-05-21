#!/usr/bin/env python3
"""
Add or remove a category from all objects in the catalog. A CSV file of
oids (first column) can be given to limit the scope of the update.

$ python examples/mass_update_categories.py --conf ubicast.json --csv media.csv --action add --category "DoNut DeeLeeTe"

If the platform is configured to not allow setting categories other than those in the pre-configured category list,
you must ensure the category you are adding is in the pre-configured list of valid categories.
"""

import argparse
import os
from pathlib import Path
import sys

try:
    from ms_client.client import MediaServerClient, MediaServerRequestError
except ModuleNotFoundError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient, MediaServerRequestError


def mass_update_categories(sys_args):
    parser = argparse.ArgumentParser(
        'mass_update_categories',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--conf',
        help='Path to the configuration file.',
        required=True,
        type=str
    )
    parser.add_argument(
        '--all',
        action='store_true',
        required=False,
        default=False,
        help='Apply the change to all objects in the catalog. '
             'Either `--all` or `--csv` must be passed but not both.'
    )
    parser.add_argument(
        '--csv',
        help='Path to CSV file; the first column is expected to be the '
             'OID. Lines starting with "#" will be ignored. Either '
             '`--all` or `--csv` must be passed but not both.',
        required=False,
        type=Path
    )
    parser.add_argument(
        '--csv-separator',
        help='CSV separator',
        default='\t',
        type=str
    )
    parser.add_argument(
        '--action',
        action='store',
        choices=['add', 'remove'],
        required=True,
        help='Whether to add or remove the given category'
    )
    parser.add_argument(
        '--category',
        action='store',
        required=True,
        help='Category to add or remove.'
    )

    args = parser.parse_args(sys_args)
    msc = MediaServerClient(args.conf)
    msc.conf['TIMEOUT'] = max(600, msc.conf['TIMEOUT'])

    # Ping
    print(f'Server url: {msc.conf["SERVER_URL"]}')
    print(f'Mediaserver version: {msc.api("/")["mediaserver"]}')

    if args.csv and not args.all:
        oids = [
            clean_line.split(args.csv_separator)[0].strip()
            for line in args.csv.read_text().strip().split('\n')
            if (clean_line := line.strip().strip('\r')) and not line.startswith('#')
        ]
    elif args.all and not args.csv:
        oids = 'all'
    else:
        raise RuntimeError('Either `--all` or `--csv` must be passed but not both.')

    answer = input(
        f'The script is about to {args.action} the "{args.category}" '
        f'{"to" if args.action == "add" else "from"} '
        f'{oids if oids == "all" else len(oids)} objects in the catalog.'
        'Proceed ? [y / n]'
    )
    if answer.lower() not in ['yes', 'y']:
        sys.exit(0)

    try:
        result = msc.api(
            'catalog/bulk-update-categories/',
            method='post',
            data={
                'oids': oids if oids == 'all' else ','.join(oids),
                'action': args.action,
                'category': args.category,
            }
        )
    except MediaServerRequestError as err:
        if 'is not a valid category' in str(err):
            print(
                f'The category you are trying to add is not in the configured list of allowed '
                f'category. Go to {msc.conf["SERVER_URL"]}/admin/settings/#id_categories_labels '
                f'and add the category to the list before running this script.'
            )
        else:
            raise err
    else:
        for oid, updated_categories in result.get('updated', {}).items():
            print(oid, updated_categories)


if __name__ == '__main__':
    mass_update_categories(sys.argv[1:])
