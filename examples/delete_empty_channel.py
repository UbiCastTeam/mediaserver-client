#!/usr/bin/env python3
'''
Script to delete empty channel from Nudgis.

To use this script clone MediaServer client, configure it and run this file.

git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/delete_empty_channel.py --conf conf.json --max-add-date YYYY-MM-DD --exclude channel_oid --dry-run
'''

import argparse
from datetime import date, datetime
import os
import sys


def empty_channel_iterator(
    channel_info,
    channel_oid_blacklist=(),
    max_date=date.today(),
    min_depth=0,
):

    for channel in channel_info.get('channels', ()):
        channel['path'] = list(channel_info.get('path', [])) + [channel['title']]
        skip_channel = (
            channel['oid'] in channel_oid_blacklist
            or datetime.strptime(channel['add_date'], '%Y-%m-%d %H:%M:%S').date() >= max_date
            or len(channel.get('channels', ())) > 0
            or len(channel.get('videos', ())) > 0
            or len(channel.get('photos', ())) > 0
            or len(channel.get('lives', ())) > 0
            or len(channel['path']) < min_depth
        )
        if not skip_channel:
            yield channel
        if channel['oid'] not in channel_oid_blacklist:
            yield from empty_channel_iterator(
                channel,
                channel_oid_blacklist=channel_oid_blacklist,
                max_date=max_date,
                min_depth=min_depth,
            )


def clean_tree(tree, deleted_oids):
    for channel in list(tree.get('channels', ())):
        if channel['oid'] in deleted_oids:
            tree['channels'].remove(channel)
        else:
            clean_tree(channel, deleted_oids)


def delete_empty_channels(msc, channel_oid_blacklist, max_date, min_depth, dry_run=False):
    tree = msc.api('catalog/get-all/')
    channel_oid_blacklist = list(channel_oid_blacklist)
    ms_url = msc.conf['SERVER_URL'] + '/permalink/'

    while True:
        empty_channel_oids = [channel['oid'] for channel in empty_channel_iterator(
            tree,
            channel_oid_blacklist=channel_oid_blacklist,
            max_date=max_date,
            min_depth=min_depth,
        )]
        if not empty_channel_oids:
            break
        deleted_oids = set(empty_channel_oids)
        if not dry_run:
            response = msc.api(
                'catalog/bulk_delete/',
                method='post',
                data=dict(oids=empty_channel_oids)
            )
            deleted_oids = {
                oid
                for oid, result in response['statuses'].items()
                if result['status'] == 200
            }
            for item in deleted_oids:
                print(f'Empty channel {ms_url}{item} has been deleted')
            if not deleted_oids:
                break
        clean_tree(tree, deleted_oids)
        if dry_run:
            for item in deleted_oids:
                print(f'[Dry run] Empty channel {ms_url}{item} will be deleted')


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument(
        '--conf',
        dest='configuration',
        help='Path to the configuration file.',
        required=True,
        type=str)

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        dest='dry_run',
        help='Enable dry mode, nothing will be deleted in dry run mode.')

    parser.add_argument(
        '--exclude',
        action='append',
        dest='exclude_oid',
        help=('Channel oid that should not be deleted. '
              'You can give this parameter multiple times to exclude multiple channels'),
        type=str)

    parser.add_argument(
        '--max-add-date',
        default=datetime.today().strftime('%Y-%m-%d'),
        dest='max_date',
        help=('All channel created prior to the given date will be deleted. '
              'Date format: "YYYY-MM-DD".'),
        type=str)

    parser.add_argument(
        '--min-depth',
        default=0,
        dest='min_depth',
        help=('Any channel that is at that depth or below will be deleted. '
              'By default it is 0 which means started from Main channels.'),
        type=int)

    args = parser.parse_args()

    print(f'Configuration path: {args.configuration}')
    print(f'Date limit: {args.max_date}')
    print(f'Blacklist channel: {args.exclude_oid}')
    print(f'Minimum depth: {args.min_depth}')
    print(f'Enable dry run: {args.dry_run}')

    #Check if configuration file exists
    if not args.configuration.startswith('unix:') and not os.path.exists(args.configuration):
        print('Invalid path for configuration file.')
        sys.exit(1)

    # Check date format
    try:
        max_date = datetime.strptime(str(args.max_date), '%Y-%m-%d').date()
    except ValueError:
        print('Incorrect data format, should be "YYYY-MM-DD".')
        sys.exit(1)

    msc = MediaServerClient(args.configuration)
    msc.check_server()

    # Check channel oid
    if args.exclude_oid:
        for oid_blacklist in args.exclude_oid:
            # Check if channel oid exists
            try:
                msc.api('channels/get/', method='get', params=dict(oid=oid_blacklist))
            except Exception as e:
                print(
                    f'Please enter valid channel oid {oid_blacklist} or check access permissions.'
                    f'Error when trying to get channel was: {e}'
                )
                sys.exit(1)
    else:
        args.exclude_oid = []
    rc = delete_empty_channels(msc, args.exclude_oid, max_date, args.min_depth, args.dry_run)
    sys.exit(rc)
