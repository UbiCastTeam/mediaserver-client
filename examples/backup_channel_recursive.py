#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to backup media from a channel and its sub channels of a MediaServer.

Backuped media are downloaded in a zip file for each media with metadata and best resource.

To use this script clone MediaServer client, configure it and run this file.
By default, files are placed in a directory named "backups" in the current directory.

git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/backup_media_from_channel.py --conf conf.json --channel c126195118a0ahqtcr04
'''

import argparse
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


def process_channel(msc, channel_info, dir_path, backuped, failed):
    # Browse channels from channel parent
    channel_items = msc.api(
        'channels/content/',
        method='get',
        params=dict(parent_oid=channel_info['oid'], content='cvp')
    )

    # Check sub channels
    for item in channel_items.get('channels', []):
        print('Check videos in channel %s %s' % (item['oid'], item['title']))
        process_channel(msc, item, dir_path, backuped, failed)

    # Backup videos and photos
    items = channel_items.get('videos', []) + channel_items.get('photos_groups', [])
    for item in items:
        media_link = msc.conf['SERVER_URL'] + '/permalink/' + item['oid'] + '/'
        print(f'// {PURPLE}{get_repr(item)}{RESET} {media_link}')
        try:
            msc.backup_media(item, dir_path)
        except Exception as err:
            print(f'{RED}{err}{RESET}')
            failed.append((item, str(err)))
        else:
            print(f'{GREEN}Backuped{RESET}')
            backuped.append(item)


def backup_media_from_channel(msc, channel_oid, dir_path):
    print('Starting backups...')

    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    backuped = list()
    failed = list()

    # Check if channel oid exists
    try:
        channel_parent = msc.api('channels/get/', method='get', params=dict(oid=channel_oid))
    except Exception as e:
        print(
            'Please enter valid channel oid or check access permissions. '
            f'Error when trying to get channel was: {e}'
        )
        return 1

    process_channel(msc, channel_parent['info'], dir_path, backuped, failed)

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
        dest='configuration',
        help='Path to the configuration file.',
        required=True,
        type=str)

    parser.add_argument(
        '--directory',
        default='backups',
        dest='dir_path',
        help='Directory in which backuped media should be added.',
        type=str)

    parser.add_argument(
        '--channel',
        dest='channel_oid',
        help='Channel oid to check.',
        required=True,
        type=str)

    args = parser.parse_args()

    print('Configuration path: %s' % args.configuration)
    print('Backups directory: %s' % args.dir_path)
    print('Parent channel oid: %s' % args.channel_oid)

    # Check if configuration file exists
    if not args.configuration.startswith('unix:') and not os.path.exists(args.configuration):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration)
    msc.check_server()
    # Increase default timeout because backups can be very disk intensive and slow the server
    msc.conf['TIMEOUT'] = max(60, msc.conf['TIMEOUT'])

    rc = backup_media_from_channel(msc, args.channel_oid, args.dir_path)
    sys.exit(rc)
