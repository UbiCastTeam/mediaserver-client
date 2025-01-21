#!/usr/bin/env python3
'''
Script to sync access permissions on media migrated from nudgis to nudgis using the transfer_media.py script
'''

import argparse
import os
import sys


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
        '--apply',
        help='Whether to apply changes',
        action='store_true',
    )

    args = parser.parse_args()

    msc_src = MediaServerClient(args.conf_src)
    src_domain = msc_src.conf['SERVER_URL'].split('/')[2]

    msc_dest = MediaServerClient(args.conf_dest)

    dest_videos = msc_dest.get_catalog(fmt='flat').get('videos', list())
    dest_external_refs = dict()
    for v in dest_videos:
        if f'nudgis:{src_domain}' in v['external_ref']:
            dest_external_refs[v['external_ref']] = v['oid']

    print(f"Found {len(dest_external_refs)} oids to sync")

    index = 0
    for external_ref, oid_dest in dest_external_refs.items():
        print(f'Processing {index + 1}/{len(dest_external_refs)}')
        index += 1

        # external_ref_prefix = f'nudgis:{src_domain}'
        # external_ref = f'{external_ref_prefix}:{oid_src}'

        oid_src = external_ref.split(':')[-1]

        if args.apply:
            sync_group_permissions(msc_src, oid_src, msc_dest, oid_dest)
        else:
            print(f"Would sync {oid_src} > {oid_dest} perms")
