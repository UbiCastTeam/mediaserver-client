#!/usr/bin/env python3
'''
This script transfers a list of media (provided as arguments or in a text file) from one Nudgis video platform to
another, while preserving the source channel tree (optionally, under an additional root channel).

Optionally (--migrate-into-personal-channels), for users which have been provisioned into the target platform, it will
migrate content located below their personal channel in the source platform into a subchannel of the personal channel
of the same user in the target platform (original tree in source personal channel will not be preserved).

This script supports preserving of:
* metadata
* annotations
* published state
* unlisted state

Note that:
* this script is in simulation mode by default, you need to run it with --apply if you want to actually run the transfer
* it will re-transcode (albeit run in low priority)
* ensure that the --personal-channels-root parameter is correct (depends on the main language of the source platform !)

Usage:
./transfer_media.py \
    --conf-src ../configs/src.json \
    --conf-dst ../configs/dst.json \
    --oid v12689655a7a850wrgs8 \
    --root-channel 'University A'

With the example above, here is the before/after location of the migrated media:
* Source path: Channel A/Channel B/v12689655a7a850wrgs8
* Target path: University A/Channel A/Channel B/v12689655a7a850wrgs8

Note: The "/" characters contained in channels titles will be replaced with "|" (because "/" is used as separator).

Other tools which can help:
* dump_users_with_personal_media.py:
    Generates a CSV file for provisioning users in the target platform.
* dump_oids.py:
    Generates a text file with all oids of the source platform to use with --oid-file
* sync_transferred_media_permissions.py:
    Synchronizes access permissions for authenticated and non-authenticated users groups only.
* regen_redirection_table.py:
    Produces a CSV file containing "previous_oid,new_oid" for each media.
'''

import argparse
import shutil
import sys
import zipfile
import json
from pathlib import Path

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


def extract_metadata_from_zip(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        return json.loads(zf.read('metadata.json'))


def find_user_by_email(msc, email):
    response = msc.api(
        'users/',
        params={
            'search': email,
            'search_exact': 'yes',
            'search_in': 'email',
        }
    )
    return response.get('users', [])


def grant_personal_channel_permission(msc, user_id, email):
    print(f'Granting personal channel permissions to user {user_id} ({email})')
    msc.api(
        'perms/edit/',
        method='post',
        data={
            'type': 'user',
            'id': user_id,
            'can_have_personal_channel': 'True',
            'can_create_media': 'True',
        }
    )


def get_or_create_personal_channel_root(msc, user_id, email):
    try:
        response = msc.api('channels/personal/', params={'id': user_id})
        return response.get('oid')
    except Exception as e:
        if getattr(e, 'status_code', None) == 403:
            grant_personal_channel_permission(msc, user_id, email)
            response = msc.api('channels/personal/', params={'id': user_id})
            return response.get('oid')
        else:
            print(f'Error retrieving personal channel for user {user_id} ({email}): {e}')
            return None


def get_or_create_subchannel(msc, title, parent_oid):
    try:
        response = msc.api('channels/get/', params={'title': title, 'parent': parent_oid})
        return response.get('info', {}).get('oid')
    except Exception as e:
        if getattr(e, 'status_code', None) == 404:
            print(f'Creating subchannel "{title}" under channel {parent_oid}')
            response = msc.api('/channels/add/', method='post', data={'title': title, 'parent': parent_oid})
            return response.get('oid')
        else:
            print(f'Error retrieving subchannel "{title}" under channel {parent_oid}: {e}')
            return None


def get_personal_subchannel_oid(msc, speaker, subchannel_title, apply=False):
    speaker_email = speaker.get('email')
    if not speaker_email:
        print(f'No email for speaker {speaker}, skipping personal channel.')
        return None

    users = find_user_by_email(msc, speaker_email)
    if not users:
        print(f'No user found with email {speaker_email}')
        return None

    user_id = users[0].get('id')
    if not user_id:
        print(f'User found but no ID for {speaker_email}')
        return None

    if not apply:
        print(f'[Dry run] Would create personal channel for {speaker_email}')
        return 'fakeoid'

    print(f'Fetching personal channel for user {user_id} ({speaker_email})')
    root_oid = get_or_create_personal_channel_root(msc, user_id, speaker_email)
    if not root_oid:
        return None
    print(f'Found personal channel root: {root_oid}')

    print(f'Fetching personal subchannel "{subchannel_title}" under channel {root_oid}')
    subchannel_oid = get_or_create_subchannel(msc, subchannel_title, root_oid)
    if not subchannel_oid:
        return None
    print(f'Found personal subchannel: {subchannel_oid}')
    return subchannel_oid


def main():
    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
        pass

    parser = argparse.ArgumentParser(description=__doc__.strip(), formatter_class=CustomFormatter)

    # Configuration
    config_group = parser.add_argument_group('configuration')
    config_group.add_argument(
        '--conf-src',
        dest='conf_src',
        help='Path to the source platform configuration file.',
        required=True,
        type=str,
    )
    config_group.add_argument(
        '--conf-dst',
        dest='conf_dst',
        help='Path to the destination platform configuration file.',
        required=True,
        type=str,
    )

    # Media selection
    media_group = parser.add_argument_group('media selection')
    media_group.add_argument(
        '--oid',
        dest='oid_list',
        help='OID of the media to transfer. Can be specified multiple times.',
        type=str,
        action='append',
    )
    media_group.add_argument(
        '--oid-file',
        dest='oid_file',
        help='Path to a file containing one OID per line.',
        type=Path,
    )

    # Migration options
    migration_group = parser.add_argument_group('migration options')
    migration_group.add_argument(
        '--root-channel',
        dest='root_channel',
        help=(
            'Optional root channel title or path on the destination platform where media will be placed into.\n'
            'Can contain multiple channels (mspath-like), like A/B/C\n'
            'Example:\n'
            '    Source path: "Faculty of medicine/Year 1"\n'
            '    Root channel: "School A/Migration"\n'
            '    Target path: "School A/Migration/Faculty of medicine/Year 1"'
        ),
        type=str,
    )
    migration_group.add_argument(
        '--no-transcode',
        dest='no_transcode',
        help=(
            'Disable media transcoding on the destination platform'
        ),
        action='store_true',
    )
    migration_group.add_argument(
        '--migrate-into-personal-channels',
        help=(
            'If set, personal content will be migrated into a subfolder of the personal channel instead of '
            'preserving the original path (and below the optional root channel).\n'
            'Note that it will flatten the personal channel tree on the destination platform.\n'
            'See --personal-subchannel-title to specify destination channel'
        ),
        action='store_true',
    )
    migration_group.add_argument(
        '--source-personal-channels-root-title',
        dest='source_personal_channels_root_title',
        help=(
            'Title of the root of personal channels on the source platform '
            '(it depends on the source platform default langage and cannot be auto-detected).\n'
            'If this is not set correctly, content may not be considered personal content.'
        ),
        default='Chaînes personnelles',
        type=str,
    )
    migration_group.add_argument(
        '--personal-subchannel-title',
        dest='personal_subchannel_title',
        help=(
            'Title of the subchannel of personal channel to create on the destination platform '
            'if using --migrate-into-personal-channels.\n'
            'Example:\n'
            '    Source path: "Personal channels/John Doe/Course A/Week 2"\n'
            '    Personal subchannel: "Migration"\n'
            '    Target path: "Personal channels/John Doe/Migration"'
        ),
        default='Migration',
        type=str,
    )

    # Temporary files and execution
    runtime_group = parser.add_argument_group('runtime options')
    runtime_group.add_argument(
        '--temp-path',
        dest='temp_path',
        help='Temporary folder to use during media migration.',
        default=Path('temp'),
        type=Path,
    )
    runtime_group.add_argument(
        '--keep-temp',
        dest='keep_temp',
        help='If set, the temporary directory for media processing will be kept.',
        action='store_true',
    )
    runtime_group.add_argument(
        '--apply',
        dest='apply',
        help='Whether to apply changes',
        action='store_true',
    )

    args = parser.parse_args()

    print('Initialize source plaform client...')
    msc_src = MediaServerClient(args.conf_src)
    src_domain = msc_src.conf['SERVER_URL'].split('/')[2]
    print(f'> {src_domain}')
    external_ref_prefix = f'nudgis:{src_domain}'

    print('Initialize destination plaform client...')
    msc_dst = MediaServerClient(args.conf_dst)
    dst_domain = msc_dst.conf['SERVER_URL'].split('/')[2]
    print(f'> {dst_domain}\n')

    oids_src = []
    # Load OIDs from file if provided
    if args.oid_file and args.oid_file.is_file():
        print(f'Reading OIDs from file: {args.oid_file}')
        with args.oid_file.open() as f:
            file_oids = [line.strip() for line in f if line.strip()]
            oids_src.extend(file_oids)

    # Append OIDs passed via CLI
    if args.oid_list:
        oids_src.extend(args.oid_list)

    # OIDs check
    oid_src_count = len(oids_src)
    if oid_src_count:
        print(f'Found {oid_src_count} OID(s) to transfer')
    else:
        sys.exit('No OIDs provided (neither via file nor CLI). Exiting.')

    print('\nRetrieve destination plaform catalog...')
    catalog = msc_dst.get_catalog(fmt='flat')
    dst_external_refs = {}
    for media_type in ('videos', 'lives', 'photos'):
        for item in catalog.get(media_type, []):
            dst_external_refs[item['external_ref']] = item['oid']
    print('Done.')

    done = 0
    skipped = 0
    failed = 0
    errors = []

    for index, oid_src in enumerate(oids_src):
        print(f'\n{BLUE}Processing {index + 1}/{oid_src_count}: {oid_src}{RESET}', flush=True)

        # Verify OID presence in destination catalog, skip if already present
        external_ref = f'{external_ref_prefix}:{oid_src}'
        if oid_dst := dst_external_refs.get(external_ref):
            print(f'Media {external_ref} already uploaded as {oid_dst}, skipping source media {oid_src}')
            print(f'{YELLOW}Skipped{RESET}')
            skipped += 1
            continue

        media_temp_dir = args.temp_path / oid_src
        step = None
        try:
            # Retrieve media
            step = 'download'
            print(f'{PURPLE}:: {step}{RESET}')
            zip_path = msc_src.backup_media(
                {'oid': oid_src},
                dir_path=media_temp_dir,
                should_be_playable=args.no_transcode
            )

            # Prepare for upload
            step = 'prepare'
            print(f'{PURPLE}:: {step}{RESET}')
            metadata = extract_metadata_from_zip(zip_path)
            src_path = metadata['path']
            upload_args = {
                'file_path': zip_path,
                'external_ref': external_ref,
                'own_media': 'no',
                'skip_automatic_subtitles': 'yes',
                'skip_automatic_enrichments': 'yes',
                'transcode': 'no' if args.no_transcode else 'yes',
                'priority': 'low',
            }

            # Migrate into personal channels if needed
            if (
                args.migrate_into_personal_channels
                and (speaker := metadata.get('speaker'))
                and args.source_personal_channels_root_title in src_path
            ):
                print('Media located in personal channel')
                # Retrieve or create related personal subchannel
                personal_subchannel_oid = get_personal_subchannel_oid(
                    msc_dst,
                    speaker,
                    args.personal_subchannel_title,
                    apply=args.apply
                )

                # upload in personal subchannel
                if personal_subchannel_oid:
                    upload_args['channel'] = personal_subchannel_oid
            else:
                print('Media located out of a personal channel')

            # Use custom root channel if specified
            if not upload_args.get('channel') and args.root_channel:
                upload_args['channel'] = f'mscpath-{args.root_channel}/{src_path}'
            # Else:
            #   No channel is provided, the original path will be preserved automatically

            # Upload media
            step = 'upload'
            print(f'{PURPLE}:: {step}{RESET}')
            if args.apply:
                try:
                    resp = msc_dst.add_media(**upload_args)
                    oid_dst = resp['oid']
                    if resp['success']:
                        print(f'File {zip_path} upload finished, object id is {oid_dst}')
                    else:
                        print(f'Upload of {zip_path} failed: {resp}')
                except MediaServerClient.RequestError as err:
                    if err.status_code == 504:
                        print(f'File {zip_path} upload finished but got code 504 (timeout); assuming it was processed.')
                    else:
                        raise
            else:
                print(f'[Dry run] Would upload {zip_path} with {upload_args}')
        except Exception as e:
            print(e)
            print(f'{RED}Failed{RESET}')
            # Keep a short part of the error for the final report
            error_msg = str(e).replace('\n', ' ')
            if len(error_msg) > 100:
                error_msg = f'...{error_msg[-100:]}'
            errors.append(f'{oid_src}: Failed to {step} media: {error_msg}')
            failed += 1
        else:
            print(f'{GREEN}Success{RESET}')
            done += 1
        finally:
            if not args.keep_temp and media_temp_dir.exists():
                print(f'Deleting {media_temp_dir}')
                shutil.rmtree(media_temp_dir)

    print(
        f'\nMedia: {GREEN}uploaded {done}{RESET}, '
        f'{YELLOW}skipped {skipped}{RESET}, '
        f'{RED}failed {failed}{RESET}.'
    )
    print('\n'.join(errors))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from ms_client.client import MediaServerClient

    sys.exit(main())
