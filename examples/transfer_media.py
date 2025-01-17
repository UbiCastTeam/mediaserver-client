#!/usr/bin/env python3
'''
Script to move one media from one video platform to another

Usage:
./transfer_media.py --conf-src ../configs/src.json --conf-dest ../configs/dest.json --oid v12689655a7a850wrgs8 --delete
'''

import argparse
import os
import shutil
import sys
import zipfile
import json
from pathlib import Path

import requests


def download_file(url, local_filename, verify=True):
    with requests.get(url, stream=True, verify=verify) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length'))
        downloaded_size = 0
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                downloaded_size += len(chunk)
                print(
                    f'Downloading {(100 * downloaded_size / total_size):.1f}%', end='\r'
                )
                f.write(chunk)
    print('Download finished')
    return local_filename


def backup_media(msc, oid, temp_path):
    if not oid.startswith('v'):
        raise Exception(f'oid {oid} is not a VOD')

    finished_marker = temp_path / 'finished.marker'
    if finished_marker.is_file():
        print(f'Skipping {temp_path} download: already done')
        return Path(finished_marker.open().read())

    media_download_dir.mkdir(parents=True)
    item = msc.api('medias/get/', params={'oid': oid})['info']
    meta_path = download_media_metadata(msc, item, temp_path, oid)
    res_path = download_media_best_resource(msc, item, temp_path, oid)

    zip_file = zipfile.ZipFile(meta_path, 'a')
    print(f'Embedding {res_path} into {meta_path}')
    zip_file.write(res_path, os.path.basename(res_path))
    zip_file.close()

    finished_marker.open('w').write(meta_path)
    print(f'media {oid} downloaded to {meta_path}')
    return meta_path


def download_media_best_resource(msc, item, media_download_dir, file_prefix):
    params = {
        'oid': item['oid'],
    }
    resources = msc.api('medias/resources-list/', params=params)['resources']
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
        raise Exception(f'Could not download any resource from list: {resources}')

    print(f'Best quality file for video {item["oid"]}: {best_quality["path"]}')
    destination_resource = os.path.join(
        media_download_dir,
        'resource - %s - %sx%s.%s'
        % (
            file_prefix,
            best_quality['width'],
            best_quality['height'],
            best_quality['format'],
        ),
    )

    if best_quality['format'] in ('youtube', 'embed'):
        # dump youtube video id or embed code to a file
        with open(destination_resource, 'w') as fo:
            fo.write(best_quality['file'])
    else:
        # download resource
        resource_url = msc.api(
            'download/',
            params=dict(oid=item['oid'], url=best_quality['path'], redirect='no'),
        )['url']

        print(f'Will download file to "{destination_resource}".')
        download_file(resource_url, destination_resource)
    return destination_resource


def download_media_metadata(msc, item, media_download_dir, file_prefix):
    metadata_zip_path = media_download_dir / f'{file_prefix}.zip'
    path = msc.download_metadata_zip(
        item['oid'],
        metadata_zip_path,
        include_annotations='all',
        include_resources_links='no',
    )
    print(f'Metadata downloaded for media {item["oid"]}: "{path}".')
    return str(path)


def extract_metadata_from_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        return json.loads(z.read('metadata.json'))


def sync_group_permissions(msc_src, oid_src, msc_dst, oid_dst):
    groups = msc_src.api(
        '/perms/get/default/',
        params={'oid': oid_src},
    )['groups']

    edit_params = {'oid': oid_dst, 'prefix': 'reference'}
    for g in groups:
        ref = g['ref']
        for perm in ['can_access_media']:
            access_perms = g['permissions'][perm]
            if access_perms.get('val') or access_perms.get('inherit_val'):
                edit_params[f'{ref}-{perm}'] = 'True'

    print(f'Synchronizing access permissions with params {edit_params}')

    r = msc_dst.api('/perms/edit/default/', method='post', data=edit_params)
    print(r)


def get_personal_channel(msc_dest, speaker, subchannel_title, apply=False):
    users = list()
    user_id = None

    if speaker.get('email'):
        speaker_email = speaker['email']

        users = msc_dest.api(
            'users/',
            params={
                'search': speaker_email,
                'search_exact': 'yes',
                'search_in': 'email',
            },
        ).get('users')

    if len(users) == 0:
        print(
            f'No user found for speaker {speaker}, leaving content at original location'
        )
    else:
        user_id = users[0]['id']

    if user_id:
        if not apply:
            print(
                f'[Dry run] Would create personal channel for {speaker_email}, returning fake oid'
            )
            return 'fakeoid'
        else:
            try:
                # WARNING: this call may create the channel, so we cannot run it in dry run mode
                print(
                    f'Searching for personal channel of user {speaker_email} with id {user_id}'
                )
                oid = msc_dest.api('channels/personal/', params={'id': user_id}).get(
                    'oid'
                )
            except Exception as e:
                if e.status_code == 403:
                    print(
                        f'Granting permission to own a personal channel to user with id {user_id}'
                    )
                    data = {
                        'type': 'user',
                        'id': user_id,
                        'can_have_personal_channel': 'True',
                        'can_create_media': 'True',
                    }
                    msc_dest.api('perms/edit/', method='post', data=data)
                    oid = msc_dest.api(
                        'channels/personal/', params={'id': user_id}
                    ).get('oid')

            # create subchannel
            try:
                oid = (
                    msc_dest.api(
                        'channels/get/',
                        params={'title': subchannel_title, 'parent': oid},
                    )
                    .get('info', {})
                    .get('oid')
                )
            except Exception as e:
                if e.status_code == 404:
                    print(
                        f'Creating subchannel {subchannel_title} in personal channel of user {user_id}'
                    )
                    oid = msc_dest.api(
                        '/channels/add/',
                        method='post',
                        data={'parent': oid, 'title': subchannel_title},
                    )['oid']
                else:
                    print(
                        f'Failed to create subchannel in personal channel of user {user_id}: {e}'
                    )
                    oid = None
            return oid


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument(
        '--conf-src',
        help='Path to the configuration file for the source platform.',
        required=True,
        type=str,
    )

    parser.add_argument(
        '--conf-dest',
        help='Path to the configuration file for the destination platform.',
        required=True,
        type=str,
    )

    parser.add_argument(
        '--temp-path',
        help='Temporary folder to use.',
        default=Path('temp'),
        type=Path,
    )

    parser.add_argument(
        '--oid',
        help='oid of the media to transfer, can be used multiple times',
        type=str,
        action='append',
    )

    parser.add_argument(
        '--oid-file',
        help='Path to file containing one oid per line',
        type=Path,
    )

    parser.add_argument(
        '--root-channel',
        help='Optional root channel to move media into',
        type=str,
        required=True,
    )

    parser.add_argument(
        '--personal-channels-root',
        help='Name of the personal channel in the source platform',
        default='Chaînes personnelles',
        type=str,
    )

    parser.add_argument(
        '--personal-subchannel',
        help='Name of the subchannel of the personal channel in the target',
        default='Migration',
        type=str,
    )

    parser.add_argument(
        '--delete-temp',
        help='Whether to keep the downloaded folder',
        action='store_true',
    )

    parser.add_argument(
        '--migrate-personal-channels',
        help='Whether to migrate personal content in a subfolder of the personal channel',
        action='store_true',
    )

    parser.add_argument(
        '--apply',
        help='Whether to apply changes',
        action='store_true',
    )

    parser.add_argument(
        '--sync-perms',
        help='Whether to synchronize access permissions at the default group level (only base groups are supported)',
        action='store_true',
    )

    args = parser.parse_args()

    msc_src = MediaServerClient(args.conf_src)
    src_domain = msc_src.conf['SERVER_URL'].split('/')[2]
    external_ref_prefix = f'nudgis:{src_domain}'

    msc_dest = MediaServerClient(args.conf_dest)

    dest_videos = msc_dest.get_catalog(fmt='flat').get('videos', list())
    dest_external_refs = dict()
    for v in dest_videos:
        dest_external_refs[v['external_ref']] = v['oid']

    oids_src = list()

    if args.oid_file and args.oid_file.is_file():
        print(f'Reading oids from {args.oid_file}')
        oids_src = args.oid_file.open().read().strip().split('\n')
    if args.oid:
        oids_src += args.oid

    oid_src_count = len(oids_src)
    if oid_src_count:
        print(f'Found {oid_src_count} oids to transfer')
    else:
        sys.exit('No oids provided, exiting')

    failed = list()
    skipped = list()
    done = list()

    for index, oid_src in enumerate(oids_src):
        print(f'Processing {index + 1}/{oid_src_count}')

        external_ref = f'{external_ref_prefix}:{oid_src}'
        if oid_dst := dest_external_refs.get(external_ref):
            print(
                f'Media {external_ref} already uploaded as {oid_dst}, skipping source media {oid_src}'
            )
            skipped.append(oid_src)
            continue

        media_download_dir = args.temp_path / oid_src
        try:
            zip_path = backup_media(msc_src, oid_src, media_download_dir)
        except Exception as e:
            error = f"Failed to backup media {oid_src}: {e}, ignoring for now"
            print(error)
            failed.append(error)
            continue

        def print_progress(progress):
            print(f'Uploading: {progress * 100:.1f}%', end='\r')

        upload_args = {
            'file_path': zip_path,
            'progress_callback': print_progress,
            'external_ref': external_ref,
            'own_media': 'no',
        }

        metadata = extract_metadata_from_zip(zip_path)
        src_path = metadata['path']

        is_personal_channel = False
        if args.migrate_personal_channels and metadata.get('speaker'):
            if args.personal_channels_root in src_path:
                is_personal_channel = True
            speaker = metadata['speaker']
            subchannel_title = args.personal_subchannel
            personal_channel_oid = get_personal_channel(
                msc_dest, speaker, subchannel_title, apply=args.apply
            )
            if personal_channel_oid is not None:
                upload_args['channel'] = personal_channel_oid

        if not upload_args.get('channel') and args.root_channel:
            upload_args['channel'] = f'mscpath-{args.root_channel}/{src_path}'

        if args.apply:
            print('Starting upload')
            resp = msc_dest.add_media(**upload_args)
            oid_dest = resp['oid']

            if args.sync_perms:
                sync_group_permissions(msc_src, oid_src, msc_dest, oid_dest)

            if resp['success']:
                print(f'File {zip_path} upload finished, object id is {oid_dest}')
            else:
                print(f'Upload of {zip_path} failed: {resp}')
        else:
            print(f'[Dry run] Would upload {zip_path} with {upload_args}')

        if args.delete_temp and media_download_dir.exists():
            print(f'Deleting {media_download_dir}')
            shutil.rmtree(media_download_dir)

        done.append(oid_src)

    print(f"Uploaded {len(done)}, skipped {len(skipped)}, failed {len(failed)} media")
    print('\n'.join(failed))
