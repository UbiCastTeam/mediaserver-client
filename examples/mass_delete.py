#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import sys

try:
    from ms_client.client import MediaServerClient
except ModuleNotFoundError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

GB = 1000 * 1000 * 1000


def format_size(size_bytes: int) -> str:
    """
    Return human-readable size with automatic suffix.
    """
    for unit in ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z'):
        if abs(size_bytes) < 1000:
            return f'{size_bytes:.1f}{unit}B'
        size_bytes /= 1000
    return f'{size_bytes:.1f}YB'


def _delete_medias(
    msc: MediaServerClient,
    oids: list[str],
    force: bool = False,
    apply: bool = False
):
    mode = '[APPLY] ' if apply else '[DRY-RUN] '
    print(f'{mode}Fetching catalog.')

    catalog = msc.get_catalog('flat')
    oids = set(oids)
    to_delete = {}
    for obj_type, objects in catalog.items():
        for obj in objects:
            if obj['oid'] in oids:
                to_delete[obj['oid']] = obj['storage_used']

    print(f'{mode}Found {len(to_delete)} objects in the catalog matching your CSV.')

    if apply:
        print(f'{mode}Starting deletion of {len(to_delete)} catalog objects.')
        params = {'oids': list(to_delete.keys())}
        if force:
            params['force'] = 'yes'
        deleted_statuses = msc.api('catalog/bulk_delete/', method='post', data=params)['statuses']

        deleted_count = 0
        deleted_size = 0
        for object_id, status in deleted_statuses.items():
            if status['status'] == 200:
                deleted_count += 1
                deleted_size += to_delete[object_id]
            else:
                print(f'{mode}Media {object_id} could not be deleted: {status.get("message")}')

        print(f'{mode}Deleted {deleted_count} VODs, freed {format_size(deleted_size)}.')
    else:
        oids = list(to_delete.keys())
        total_size = sum(to_delete.values())
        print(f'{mode}Would have deleted {len(oids)} VODs: {oids}')
        print(
            f'{mode}Deleting these VODs would have freed {format_size(total_size)}.'
        )


def delete_medias_from_csv(sys_args):
    parser = argparse.ArgumentParser(
        'mass_delete',
        description='''
            Delete all media described by oids in a CSV file (first column)

            WARNING: ENABLE THE RECYCLE-BIN ON YOUR PLATFORM BEFORE RUNNING THIS SCRIPT.
            IF YOU DON'T, OR IF YOU USE THE "--force" FLAG, YOUR ACTIONS WILL BE IRREVERSIBLE.

            By default, the script just reports the space that would be freed (no actual
            deletions).

            $ python examples/mass_delete.py --conf ubicast.json --csv media.csv
            v12345649684
            ...
            Deleting 7 media would have freed 4.1 GB

            To actually perform the deletions, pass "--apply":
            $ python examples/mass_delete.py --conf ubicast.json --csv media.csv --apply

            If you've made a mistake, assuming the recycle-bin is active on your platform
            and you didn't use "--force", you can revert your actions by manually selecting
            and restoring content from the recycle-bin.
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--conf',
        help='Path to the configuration file.',
        required=True,
        type=str
    )
    parser.add_argument(
        '--csv',
        help='Path to CSV file; the first column is expected to be the OID. '
             'Lines starting with "#" will be ignored',
        required=True,
        type=Path
    )
    parser.add_argument(
        '--csv-separator',
        help='CSV separator',
        default='\t',
        type=str
    )
    parser.add_argument(
        '--force',
        action='store_true',
        default=False,
        help='Bypass the recycle-bin. With this flag, videos will be deleted without the '
             'possibility of restoration, even if the recycle-bin is activated on the '
             'platform. Beware, if the recycle-bin is not activated on the platform, '
             'medias will be deleted forever whether this flag is passed or not. For '
             'videos to be deleted to the recycle-bin, you need to activate the '
             'recycle-bin on the platform AND omit this flag.'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        default=False,
        help='Really delete; without this flag, an estimation of the freed space will be '
             'printed instead.'
    )

    args = parser.parse_args(sys_args)
    msc = MediaServerClient(args.conf)
    msc.conf['TIMEOUT'] = max(600, msc.conf['TIMEOUT'])

    # Ping
    print(f'Server url: {msc.conf["SERVER_URL"]}')
    print(f'Mediaserver version: {msc.api("/")["mediaserver"]}')
    oids = [
        clean_line.split(args.csv_separator)[0].strip()
        for line in args.csv.read_text().strip().split('\n')
        if (clean_line := line.strip().strip('\r')) and not line.startswith('#')
    ]

    if args.apply:
        answer = input(
            f'The script is running in normal mode. {len(oids)} medias will be deleted.\n'
            'Please ensure that the recycle-bin is enabled on your platform '
            f'{msc.conf["SERVER_URL"]}/admin/settings/#id_trash_enabled \n'
            'Proceed ? [y / n]'
        )
        if answer.lower() not in ['yes', 'y']:
            sys.exit(0)
    else:
        print(
            'The script is running in dry-run mode. No media will be deleted. '
            f'A report of the storage used by the {len(oids)} medias in your CSV will be '
            'generated.'
        )
    _delete_medias(msc, oids, force=args.force, apply=args.apply)


if __name__ == '__main__':
    delete_medias_from_csv(sys.argv[1:])
