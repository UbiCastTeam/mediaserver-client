#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to backup media (metadata and best resource) from a MediaServer.

To use this script clone MediaServer client, configure it and run this file.
By default, files are placed in a directory named "backups" in the current directory.

git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/backup_media.py --conf conf.json --date 2020-01-01
'''

import argparse
import datetime
import os
import sys
import unidecode


# Terminal colors
if sys.stdout.isatty():
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    PURPLE = '\033[35m'
    TEAL = '\033[36m'
    RESET = '\033[0m'
else:
    RED = GREEN = YELLOW = BLUE = PURPLE = TEAL = RESET = ''


OBJECT_TYPES = {'v': 'video', 'l': 'live', 'p': 'photos', 'c': 'channel'}


def get_repr(item):
    return '%s %s "%s%s"' % (
        OBJECT_TYPES[item['oid'][0]],
        item['oid'],
        item['title'][:40],
        ('...' if len(item['title']) > 40 else '')
    )


def get_prefix(item):
    return unidecode.unidecode(item['title'][:57].strip()).replace('/', '|') + ' - ' + item['oid']


def make_backup(msc, dir_path, limit_date, use_add_date=False, enable_delete=False):
    print('Starting backups...')
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    date_field = 'add_date' if use_add_date else 'creation'

    more = True
    start = datetime.datetime.strftime(limit_date, '%Y-%m-%d 00:00:00')
    index = 0
    backuped = list()
    failed = list()
    while more:
        print('//// Making request on latest (start=%s)' % start)
        response = msc.api('latest/', params=dict(start=start, order_by=date_field, content='vlp', count=20))
        for item in response['items']:
            index += 1
            media_link = msc.conf['SERVER_URL'] + '/permalink/' + item['oid'] + '/'
            print(f'// {PURPLE}Media {index}:{RESET} "{media_link}" {get_repr(item)}')
            media_date = datetime.datetime.strptime(item[date_field][0:10], '%Y-%m-%d').date()
            if media_date > limit_date:
                print('No backup for media %s because creation date %s is newer than backup date %s' % (
                    get_repr(item), item['creation'], limit_date))
            else:
                try:
                    msc.backup_media(item, dir_path)
                except Exception as err:
                    print(f'{RED}{err}{RESET}')
                    failed.append((item, str(err)))
                    if enable_delete:
                        print('Media %s will not be deleted because it has not been successfully downloaded.' % (
                            get_repr(item)))
                else:
                    print(f'{GREEN}Backuped{RESET}')
                    backuped.append(item)
                    if enable_delete:
                        try:
                            msc.api(
                                'medias/delete/',
                                method='post',
                                data=dict(oid=item['oid'], delete_metadata='yes', delete_resources='yes', force='yes')
                            )
                        except Exception as e:
                            print('Failed to delete media %s: %s' % (get_repr(item), e))
                        else:
                            print('Media %s has been deleted successfully from MediaServer.' % get_repr(item))
        start = response['max_date']
        more = response['more']
    print('Done.\n')

    if backuped:
        print('%sMedia backuped successfully (%s):%s' % (GREEN, len(backuped), RESET))
        for item in backuped:
            print('  [%sOK%s] %s' % (GREEN, RESET, get_repr(item)))
    if failed:
        print('%sMedia backups failed (%s):%s' % (RED, len(failed), RESET))
        for item, error in failed:
            print('  [%sKO%s] %s: %s' % (RED, RESET, get_repr(item), error))
        print('%sSome media were not backuped.%s' % (YELLOW, RESET))
        return 1
    if backuped:
        print('%sAll media have been backuped successfully.%s' % (GREEN, RESET))
    else:
        print('No media to backup.')
    return 0


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--conf',
        dest='configuration_path',
        help='Path to the configuration file.',
        required=True,
        type=str)
    parser.add_argument(
        '--date',
        dest='limit_date',
        help=('All media created/added (depending on "--use-add-date") prior to the given date will be backuped. '
              'Date format: "YYYY-MM-DD".'),
        required=True,
        type=str)
    parser.add_argument(
        '--directory',
        default='backups',
        dest='dir_path',
        help='Directory in which backuped media should be added.',
        type=str)
    parser.add_argument(
        '--use-add-date',
        action='store_true',
        default=False,
        dest='use_add_date',
        help='Use add date of media instead of creation date.')
    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        dest='enable_delete',
        help='Delete media in MediaServer once successfully backuped.')

    args = parser.parse_args()

    print('Configuration path: %s' % args.configuration_path)
    print('Date limit: %s' % args.limit_date)
    print('Backups directory: %s' % args.dir_path)
    print('Enable delete: %s' % args.enable_delete)

    # Check if file exists
    if not os.path.exists(args.configuration_path):
        print('Invalid path for configuration file.')
        sys.exit(1)

    # Check date format
    try:
        limit_date = datetime.datetime.strptime(str(args.limit_date), '%Y-%m-%d').date()
    except ValueError:
        print('Incorrect data format, should be "YYYY-MM-DD".')
        sys.exit(1)

    msc = MediaServerClient(args.configuration_path)
    msc.check_server()
    # Increase default timeout because backups can be very disk intensive and slow the server
    msc.conf['TIMEOUT'] = max(60, msc.conf['TIMEOUT'])

    rc = make_backup(msc, args.dir_path, limit_date, args.use_add_date, args.enable_delete)
    sys.exit(rc)
