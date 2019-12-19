#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to backup media (metadata and best resource) from a MediaServer.

To use this script clone MediaServer client, configure it and run this file.
git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/backup_media.py --conf conf.json --date 2020-01-01

Dependencies:
python3-unidecode
'''

import argparse
import datetime
import os
import requests
import subprocess
import sys
import unidecode


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


def get_prefix(item):
    return unidecode.unidecode(item['title'][:57].strip()) + ' - ' + item['oid']


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
            print('// %sMedia %s:%s "%s" %s' % (PURPLE, index, DEFAULT, media_link, get_repr(item)))
            media_date = datetime.datetime.strptime(item[date_field][0:10], '%Y-%m-%d').date()
            if media_date > limit_date:
                print('No backup for media %s because creation date %s is newer than backup date %s' % (get_repr(item), item['creation'], limit_date))
                continue

            channels = msc.api('channels/path/', params=dict(oid=item['oid']))['path']

            file_prefix = get_prefix(item)
            media_backup_dir = dir_path
            for channel in channels:
                media_backup_dir += '/' + get_prefix(channel)
            media_backup_dir += '/' + file_prefix
            if not os.path.exists(media_backup_dir):
                os.makedirs(media_backup_dir)

            try:
                download_media_best_resource(msc, item, media_backup_dir, file_prefix)
                resource_dl_error = None
            except Exception as e:
                error = 'Failed to download resource: ' + str(e)
                print('%s%s%s' % (RED, error, DEFAULT))
                resource_dl_error = error

            try:
                download_media_metadata(msc, item, media_backup_dir, file_prefix)
                metadata_dl_error = None
            except Exception as e:
                error = 'Failed to download metadata: ' + str(e)
                print('%s%s%s' % (RED, error, DEFAULT))
                metadata_dl_error = error

            # Delete media if enable delete and resource and metadata are OK
            if resource_dl_error or metadata_dl_error:
                error = ''
                if resource_dl_error:
                    error += ' ' + resource_dl_error
                if metadata_dl_error:
                    error += ' ' + metadata_dl_error
                failed.append((item, error))
                if enable_delete:
                    print('Media %s will not be deleted because it has not been successfully downloaded.' % get_repr(item))
            else:
                backuped.append(item)
                if enable_delete:
                    try:
                        msc.api('medias/delete/', method='post', data=dict(oid=item['oid'], delete_metadata='yes', delete_resources='yes'))
                    except Exception:
                        print('Failed to delete media %s')
                print('Media %s has been deleted successfully from MediaServer.' % get_repr(item))
        start = response['max_date']
        more = response['more']
    print('Done.\n')

    if backuped:
        print('%sMedia backuped successfully (%s):%s' % (GREEN, len(backuped), DEFAULT))
        for item in backuped:
            print('  [%sOK%s] %s' % (GREEN, DEFAULT, get_repr(item)))
    if failed:
        print('%sMedia backups failed (%s):%s' % (RED, len(failed), DEFAULT))
        for item, error in failed:
            print('  [%sKO%s] %s:%s' % (RED, DEFAULT, get_repr(item), error))
        print('%sSome media were not backuped.%s' % (YELLOW, DEFAULT))
        return 1
    if backuped:
        print('%sAll media have been backuped successfully.%s' % (GREEN, DEFAULT))
    else:
        print('No media to backup.')
    return 0


def download_media_best_resource(msc, item, media_backup_dir, file_prefix):
    if item['oid'][0] != 'v':
        return  # item is not a video
    resources = msc.api('medias/resources-list/', params=dict(oid=item['oid']))['resources']
    resources.sort(key=lambda a: -a['file_size'])
    if not resources:
        print('Media has no resources.')
        return
    best_quality = None
    for r in resources:
        if r['protocol'] == 'http' and r['format'] != 'm3u8':
            best_quality = r
            break
    if not best_quality:
        print('%sWarning: No resource file can be downloaded for video %s!%s' % (YELLOW, get_repr(item), DEFAULT))
        print('Resources: %s' % resources)
        raise Exception('Could not download any resource from list: %s.' % resources)

    print('Best quality file for video %s: %s' % (get_repr(item), best_quality['file']))
    destination_resource = '%s/%s - %sx%s.%s' % (media_backup_dir, file_prefix, best_quality['width'], best_quality['height'], best_quality['format'])

    if best_quality['format'] in ('youtube', 'embed'):
        # dump youtube video id or embed code to a file
        with open(destination_resource, 'w') as fo:
            fo.write(best_quality['file'])
    else:
        url_resource = msc.api('download/', params=dict(oid=item['oid'], url=best_quality['file'], redirect='no'))['url']
        if os.path.exists(destination_resource):
            local_size = os.path.getsize(destination_resource)
            req = requests.head(url_resource, verify=False)
            if local_size == int(req.headers.get('Content-Length', '0')):
                print('File is already downloaded: "%s".' % destination_resource)
                return

        print('Will download file to "%s".' % destination_resource)
        p_resource = subprocess.run(['wget', '--no-check-certificate', url_resource, '-O', destination_resource])
        if p_resource.returncode != 0:
            raise Exception('The wget command exited with code %s.' % p_resource.returncode)


def download_media_metadata(msc, item, media_backup_dir, file_prefix):
    destination_metadata = '%s/%s.zip' % (media_backup_dir, file_prefix)
    path = msc.download_metadata_zip(item['oid'], destination_metadata, include_annotations='all', include_resources_links='no')
    print('Metadata downloaded for media %s: "%s".' % (get_repr(item), path))


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
        help='All media created/added (depending on "--use-add-date") prior to the given date will be backuped. Date format: "YYYY-MM-DD".',
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
    msc.conf['TIMEOUT'] = 30  # Increase timeout because backups can be very disk intensive and slow the server

    rc = make_backup(msc, args.dir_path, limit_date, args.use_add_date, args.enable_delete)
    sys.exit(rc)
