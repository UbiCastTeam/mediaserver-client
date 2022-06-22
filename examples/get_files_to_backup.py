#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to get the list of files to backup for a given period (one week by default).
This script must be runned on the MediaServer system by the root user or by the MediaServer user.

To use this script clone MediaServer client and run this file.
git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/get_files_to_backup.py --user msuser --period 14days
'''

import argparse
import datetime
import os
import re
import sys


# Terminal colors
if os.environ.get('LS_COLORS') is not None:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    TEAL = '\033[96m'
    DEFAULT = '\033[0m'
else:
    RED = GREEN = YELLOW = BLUE = PURPLE = TEAL = DEFAULT = ''


OBJECT_TYPES = {'v': 'video', 'l': 'live', 'p': 'photos', 'c': 'channel'}


def get_repr(item):
    return '%s %s "%s%s"' % (OBJECT_TYPES[item['oid'][0]], item['oid'], item['title'][:40], ('...' if len(item['title']) > 40 else ''))


def get_item_folder_name(item):
    if item.get('folder_name'):
        return item['folder_name']
    elif item.get('thumb'):
        # old API, guess folder name with preview image url
        m = re.match(r'^http[s]+://.+/public/(\w+/\w+)/.+$', item['thumb'])
        if m:
            return m.groups()[0]


def print_path_if_exists(path, file=None):
    if os.path.exists(path):
        print(path, file=file or sys.stdout)


def get_files_to_backup(msc, user, from_date, to_date, fout=None, verbose=False):
    if from_date > to_date:
        tmp_date = to_date
        to_date = from_date
        from_date = tmp_date

    print('--- Files list from %s to %s ----' % (from_date, to_date))
    to_date += datetime.timedelta(days=1)  # include last day
    # media and channels files
    more = True
    start = to_date.strftime('%Y-%m-%d 00:00:00')
    index = 0
    channels_oids = list()
    while more:
        if verbose:
            print('# Making request on latest (start=%s)' % start)
        response = msc.api('latest/', params=dict(start=start, order_by='added', content='vlp', count=20))
        start = response['max_date']
        more = response['more']
        for item in response['items']:
            index += 1
            if verbose:
                print('# %sMedia %s:%s "%s" %s' % (PURPLE, index, DEFAULT, item['add_date'], get_repr(item)))
            add_date = datetime.datetime.strptime(item['add_date'].split(' ')[0], '%Y-%m-%d').date()
            if add_date < from_date:
                more = False
                if verbose:
                    print('# Media was not added in the requested period, stopping loop.')
                break
            # get channels files
            channels = msc.api('channels/path/', params=dict(oid=item['oid']))['path']
            for channel in channels:
                if channel['oid'] not in channels_oids:
                    channels_oids.append(channel['oid'])
                    info = msc.api('channels/get/', params=dict(oid=channel['oid']))['info']
                    folder_name = get_item_folder_name(info)
                    if folder_name:
                        print_path_if_exists('/home/%s/msinstance/media/public/%s/' % (user, folder_name), fout)
                        print_path_if_exists('/home/%s/msinstance/media/protected/%s/' % (user, folder_name), fout)
                    elif verbose:
                        print('# No folder name found for channel %s.' % get_repr(info))
            # get media files
            folder_name = get_item_folder_name(item)
            if folder_name:
                print_path_if_exists('/home/%s/msinstance/media/public/%s/' % (user, folder_name), fout)
                print_path_if_exists('/home/%s/msinstance/media/protected/%s/' % (user, folder_name), fout)
            elif verbose:
                print('# No folder name found for media %s.' % get_repr(item))
            # get media resources
            if item['oid'][0] == 'v':
                resources = msc.api('medias/resources-list/', params=dict(oid=item['oid']))['resources']
                for res in resources:
                    if res['format'] in ('mp4', 'mp3'):
                        m = re.match(r'^http[s]+://.+/(resources/.+)$', res['file'])
                        if m:
                            print_path_if_exists('/home/%s/msinstance/media/%s' % (user, m.groups()[0]), fout)
    # stats files
    cur_date = from_date
    while cur_date <= to_date:
        print_path_if_exists('/home/%s/msinstance/stats/%s/%s/%s/' % (user, cur_date.year, cur_date.month, cur_date.day), fout)
        cur_date += datetime.timedelta(days=1)

    return 0


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--user',
        dest='user',
        help='Unix user name. Default is `msuser`.',
        required=False,
        default='msuser',
        type=str)
    parser.add_argument(
        '--period',
        dest='period',
        help='All files from media added in the given period will be returned. Allowed values: `Xdays` (X has to be replaced with an integer), `YYYY-MM-DD_YYYY-MM-DD` (pick media between the two dates). Default is `7days`.',
        required=False,
        default='7days',
        type=str)
    parser.add_argument(
        '--out',
        dest='output',
        help='Path to a file in which the list will be written. Default is the proccess stdout.',
        required=False,
        type=str)
    parser.add_argument(
        '--verbose',
        dest='verbose',
        help='Display more informations. If --out is given, verbose is enabled.',
        action='store_true',
        default=False)

    args = parser.parse_args()

    print('User: %s' % args.user)
    print('Period: %s' % args.period)
    print('Output: %s' % args.output)
    print('Verbose: %s' % args.verbose)

    # Check date format
    m = re.match(r'^(\d+)days$', args.period)
    if m:
        to_date = datetime.date.today()
        from_date = to_date - datetime.timedelta(days=int(m.groups()[0]))
    else:
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})_(\d{4})-(\d{2})-(\d{2}$)', args.period)
        if m:
            try:
                from_date = datetime.date(year=m.groups()[0], month=m.groups()[1], day=m.groups()[2])
                to_date = datetime.date(year=m.groups()[3], month=m.groups()[4], day=m.groups()[5])
            except ValueError:
                print('Incorrect date format, should be "YYYY-MM-DD".')
                sys.exit(1)
        else:
            print('Incorrect period value.')
            sys.exit(1)

    msc = MediaServerClient('unix:%s' % args.user)
    msc.check_server()

    verbose = args.verbose or args.output
    if args.output:
        with open(args.output, 'w') as fout:
            rc = get_files_to_backup(msc, user=args.user, from_date=from_date, to_date=to_date, fout=fout, verbose=verbose)
    else:
        rc = get_files_to_backup(msc, user=args.user, from_date=from_date, to_date=to_date, verbose=verbose)
    sys.exit(rc)
