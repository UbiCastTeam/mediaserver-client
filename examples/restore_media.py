#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to restore media from a directory to a MediaServer.
Media to restore should be zip files with their resource inside (as produced by the backup_media script).

To use this script clone MediaServer client, configure it and run this file.

git clone https://github.com/UbiCastTeam/mediaserver-client
cd mediaserver-client
python3 examples/restore_media.py --conf conf.json --path backups --channel 'import test'
'''

import argparse
import json
import os
import sys
import traceback
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


def restore_path(msc, path, top_channel_path):
    if not os.path.exists(path):
        print('%sERROR:%s Requested directory does not exist.' % (RED, DEFAULT))
        return 1

    print('\nGetting list of media to restore...')
    to_restore = list()
    if os.path.isdir(path):
        for dir_path, dir_names, file_names in os.walk(path, followlinks=True):
            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                if not file_path.endswith('.zip'):
                    print('Path %s ignored (not a zip file).' % file_path)
                else:
                    to_restore.append(file_path)
    elif os.path.isfile(path):
        if not path.endswith('.zip'):
            print('Path %s ignored (not a zip file).' % path)
        else:
            to_restore.append(path)
    else:
        print('%sERROR:%s Requested path is neither a directory neither a file.' % (RED, DEFAULT))
        return 1
    if not to_restore:
        print('No valid file to restore.')
        return 1
    print('Number of media to restore: %s.' % len(to_restore))

    print('\nStarting restoration...')
    restored = list()
    existing = list()
    failed = list()
    for index, file_path in enumerate(to_restore):
        print('Media %s / %s (%s %%):' % (index + 1, len(to_restore), round(100 * (index + 1) / len(to_restore))))
        try:
            is_new, url = _restore_file(msc, file_path, top_channel_path)
        except Exception as e:
            print('%s%s: %s%s' % (RED, e.__class__.__name__, e, DEFAULT))
            traceback.print_exc()
            failed.append((file_path, str(e)))
        else:
            if is_new:
                restored.append((file_path, url))
            else:
                existing.append((file_path, url))
    print('Done.\n')

    print('Report:')
    if restored:
        print('%sMedia restored successfully (%s):%s' % (GREEN, len(restored), DEFAULT))
        for path, url in restored:
            print('  [%sOK%s] %s: %s' % (GREEN, DEFAULT, path, url))
    if existing:
        print('%sMedia already existing (%s):%s' % (GREEN, len(existing), DEFAULT))
        for path, url in existing:
            print('  [%sOK%s] %s: %s' % (GREEN, DEFAULT, path, url))
    if failed:
        print('%sMedia restoration failed (%s):%s' % (RED, len(failed), DEFAULT))
        for path, error in failed:
            print('  [%sKO%s] %s: %s' % (RED, DEFAULT, path, error))
        print('%sSome media were not restored.%s' % (RED, DEFAULT))
        return 1
    print('%sAll media were restored.%s' % (GREEN, DEFAULT))
    return 0


def _restore_file(msc, path, top_channel_path):
    print('Restoring media from file "%s"...' % path)
    old_version = msc.get_server_version() < (9, 0, 0)
    special_res = None
    with zipfile.ZipFile(path, 'r') as zip_file:
        # CRC check of zip file
        files_with_error = zip_file.testzip()
        if files_with_error:
            raise Exception('Some files have errors in the zip file: %s' % files_with_error)
        # Get media metadata
        metadata_json = zip_file.open('metadata.json').read()
        # Check if media is using special resource
        if old_version:
            for name in zip_file.namelist():
                if name.endswith('.youtube'):
                    special_res = 'YouTube: ' + zip_file.open(name).read()
                    break
                elif name.endswith('.embed'):
                    special_res = 'Embed: ' + zip_file.open(name).read()
                    break
    metadata = json.loads(metadata_json)
    if not metadata.get('path') and not metadata.get('category'):
        raise Exception('Media has no channel defined in metadata.json file.')
    is_new = False
    url = None
    if metadata.get('path') or top_channel_path:
        channel_path = metadata['path'] if metadata.get('path') else metadata['category']
        if top_channel_path:
            channel_path = top_channel_path + '/' + channel_path
        # check if media already exists
        if old_version:
            print('The server version is too old, unable to check media existence.')
        else:
            response = msc.api('medias/get/', params=dict(parents=channel_path, title=metadata['title']), ignore_404=True)
            if response:
                oid = response['info']['oid']
                url = msc.conf['SERVER_URL'] + '/permalink/' + oid + '/'
                print('Media already exists, it will not be added twice.')
                if oid.startswith('v'):
                    # check resource if media is a video
                    resources = msc.api('medias/resources-list/', params=dict(oid=oid))['resources']
                    if not resources:
                        raise Exception('The media already exist but has no resources. Please restore the resource manually in media "%s".' % url)
        channel_target = 'mscpath-' + channel_path
    else:
        channel_target = metadata['category']
    # add media if needed
    if not url:
        item = msc.add_media(file_path=path, channel=channel_target, transcode='yes', detect_slides='no', autocam='no')
        oid = item['oid']
        url = msc.conf['SERVER_URL'] + '/permalink/' + oid + '/'
        is_new = True
    if old_version and special_res:
        raise Exception('The media metadata have been restored but the media uses a resource that should be restored manually:\n%s\nMedia url: %s' % (special_res, url))
    print('Media restored: "%s".' % url)
    return is_new, url


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
        '--path',
        default='path',
        dest='path',
        help='Directory in which media should be restored.',
        type=str)
    parser.add_argument(
        '--channel',
        dest='channel',
        help='Path to an existing channel in which all restored media should be added. The path should be splitted by slashes and can contain slug or title. Example: "Channel A/Channel B". If no value is given, media will be restored in their original channel.',
        required=False,
        type=str)

    args = parser.parse_args()

    print('Configuration path: %s' % args.configuration_path)
    print('Path: %s' % args.path)
    print('Channel: %s' % args.channel)

    # Check if file exists
    if not os.path.exists(args.configuration_path):
        print('Invalid path for configuration file.')
        sys.exit(1)

    msc = MediaServerClient(args.configuration_path)
    msc.get_server_version()
    msc.conf['TIMEOUT'] = 60  # Increase timeout because backups can be very disk intensive and slow the server

    rc = restore_path(msc, args.path, args.channel)
    sys.exit(rc)
