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


Dependencies:
python3-unidecode
'''

import argparse
import os
import sys
import requests
import subprocess
import unidecode
import zipfile

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
    return unidecode.unidecode(item['title'][:57].strip()).replace('/', '|') + ' - ' + item['oid']


def backup_media(item, dir_path):
    channels = msc.api('channels/path/', params=dict(oid=item['oid']))['path']

    media_chan_path = [channel['title'] for channel in channels]
    media_backup_dir = os.path.join(dir_path, *[get_prefix(channel) for channel in channels])
    if not os.path.exists(media_backup_dir):
        os.makedirs(media_backup_dir)

    file_prefix = get_prefix(item)
    zip_path = os.path.join(media_backup_dir, file_prefix + '.zip')
    metadata_zip_size = 0
    best_resource_size = 0
    if os.path.exists(zip_path):
        # get file size from existing zip to skip downloads if useless
        try:
            zip_file = zipfile.ZipFile(zip_path, 'r')
        except Exception as e:
            print('%sFailed to open existing zip file: %s%s' % (RED, e, DEFAULT))
        else:
            for name in zip_file.namelist():
                if name == 'metadata-size.txt':
                    try:
                        metadata_zip_size = int(zip_file.open(name).read())
                    except Exception as e:
                        print('%sFailed to parse metadata from existing zip file: %s%s' % (RED, e, DEFAULT))
                elif name.startswith('resource -'):
                    file_info = zip_file.getinfo(name)
                    best_resource_size = file_info.file_size
            zip_file.close()

    try:
        meta_path = download_media_metadata(msc, item, media_backup_dir, file_prefix, metadata_zip_size)
    except Exception as e:
        raise Exception('Failed to download metadata: %s' % e)

    if meta_path:
        best_resource_size = 0  # force resource download if the metadata has changed
    try:
        res_path = download_media_best_resource(msc, item, media_backup_dir, file_prefix, best_resource_size)
    except Exception as e:
        raise Exception('Failed to download resource: %s' % e)

    if res_path and not meta_path:
        # force zip download if the best resource has changed and if the metadata were not already downloaded
        try:
            meta_path = download_media_metadata(msc, item, media_backup_dir, file_prefix, 0)
        except Exception as e:
            raise Exception('Failed to download metadata: %s' % e)

    if res_path or meta_path:
        # the metadata or the best resource has changed, put resource in zip and update info
        if not meta_path and res_path:
            raise Exception('The metadata should have been downloaded.')
        metadata_size = os.path.getsize(meta_path)

        # add resource in zip and some other informations
        try:
            zip_file = zipfile.ZipFile(meta_path, 'a')
        except Exception as e:
            raise Exception('Failed to open downloaded zip file: %s' % e)
        zip_file.writestr('metadata-size.txt', str(metadata_size))
        zip_file.writestr('metadata-path.txt', '/'.join(media_chan_path))
        if res_path:
            zip_file.write(res_path, os.path.basename(res_path))
        zip_file.close()

        # CRC check of zip file
        zip_file = zipfile.ZipFile(meta_path, 'r')
        files_with_error = zip_file.testzip()
        if files_with_error:
            raise Exception('Some files have errors in the zip file: %s' % files_with_error)
        zip_file.close()

        # rename zip file and remove temporary files
        os.rename(meta_path, zip_path)
        if res_path:
            os.remove(res_path)
    else:
        print('Media was already correctly backuped.')


def download_media_best_resource(msc, item, media_backup_dir, file_prefix, local_size=0):
    if item['oid'][0] != 'v':
        return  # item is not a video
    resources = msc.api('medias/resources-list/', params=dict(oid=item['oid']))['resources']
    resources.sort(key=lambda a: -a['file_size'])
    if not resources:
        print('Media has no resources.')
        return
    best_quality = None
    for r in resources:
        if r['format'] != 'm3u8':
            best_quality = r
            break
    if not best_quality:
        print('%sWarning: No resource file can be downloaded for video %s!%s' % (YELLOW, get_repr(item), DEFAULT))
        print('Resources: %s' % resources)
        raise Exception('Could not download any resource from list: %s.' % resources)

    print('Best quality file for video %s: %s' % (get_repr(item), best_quality['file']))
    destination_resource = os.path.join(media_backup_dir, 'resource - %s - %sx%s.%s' % (file_prefix, best_quality['width'], best_quality['height'], best_quality['format']))

    if best_quality['format'] in ('youtube', 'embed'):
        # dump youtube video id or embed code to a file
        with open(destination_resource, 'w') as fo:
            fo.write(best_quality['file'])
    else:
        # download resource
        url_resource = msc.api('download/', params=dict(oid=item['oid'], url=best_quality['file'], redirect='no'))['url']
        if os.path.exists(destination_resource):
            local_size = os.path.getsize(destination_resource)
        if local_size:
            req = requests.head(url_resource, verify=msc.conf['VERIFY_SSL'])
            if req.headers.get('Content-Length') == str(local_size):
                print('File is already downloaded: "%s".' % destination_resource)
                return

        print('Will download file to "%s".' % destination_resource)
        if msc.conf['VERIFY_SSL']:
            cmd = ['wget', url_resource, '-O', destination_resource]
        else:
            cmd = ['wget', '--no-check-certificate', url_resource, '-O', destination_resource]
        p_resource = subprocess.run(cmd)
        if p_resource.returncode != 0:
            raise Exception('The wget command exited with code %s.' % p_resource.returncode)
    return destination_resource


def download_media_metadata(msc, item, media_backup_dir, file_prefix, local_size=0):
    if local_size:
        params = dict(oid=item['oid'], annotations='all', resources='no')
        req = msc.api('medias/get/zip/', method='head', params=params, timeout=3600)
        if req.headers.get('Content-Length') == str(local_size):
            print('Skipping download of zip file for %s because the file already exists and has the correct size.' % item['oid'])
            return

    destination_metadata = os.path.join(media_backup_dir, 'metadata %s.zip' % file_prefix)
    path = msc.download_metadata_zip(item['oid'], destination_metadata, include_annotations='all', include_resources_links='no')
    print('Metadata downloaded for media %s: "%s".' % (get_repr(item), path))
    return path


def process_channel(msc, channel_info, dir_path, backuped, failed):

    # Browse channels from channel parent
    channel_items = msc.api('channels/content/', method='get', params=dict(parent_oid=channel_info['oid'], content='cvp'))

    # Check sub channels
    for entry in channel_items.get('channels', []):
        print('Check videos in channel %s %s' % (entry['oid'], entry['title']))
        process_channel(msc, entry, dir_path, backuped, failed)

    # Backup videos and photos
    items = channel_items.get('videos', []) + channel_items.get('photos_groups', [])
    for entry in items:
        try:
            backup_media(entry, dir_path)
        except Exception as e:
            print('%s%s%s' % (RED, e, DEFAULT))
            failed.append((entry, str(e)))
        else:
            backuped.append(entry)


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
        print('Please enter valid channel oid or check access permissions. Error when trying to get channel was: %s' % e)
        return 1

    process_channel(msc, channel_parent['info'], dir_path, backuped, failed)

    if backuped:
        print('%sMedia backuped successfully (%s):%s' % (GREEN, len(backuped), DEFAULT))
        for item in backuped:
            print('  [%sOK%s] %s' % (GREEN, DEFAULT, get_repr(item)))
    if failed:
        print('%sMedia backups failed (%s):%s' % (RED, len(failed), DEFAULT))
        for item, error in failed:
            print('  [%sKO%s] %s: %s' % (RED, DEFAULT, get_repr(item), error))
        print('%sSome media were not backuped.%s' % (YELLOW, DEFAULT))
        return 1
    if backuped:
        print('%sAll media have been backuped successfully.%s' % (GREEN, DEFAULT))
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
