#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Example script that mass moves media into a channel based on a criteria (e.g. here a specific external_ref prefix)
'''
import os
import sys


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    print(msc.api('/'))

    more = True
    start = ''
    index = 0

    external_ref_prefix = 'examplevalue'
    target_channel_oid = 'c12345678910'

    while more:
        print('//// Making request on latest (start=%s)' % start)
        response = msc.api('latest/', params={'start': start, 'content': 'v', 'count': 20})
        for item in response['items']:
            oid = item['oid']
            index += 1
            print('// Media %s' % index)
            external_ref = msc.api('medias/get/', params={'oid': oid, 'full': 'yes'})['info'].get('external_ref')
            if external_ref:
                if external_ref.startswith(external_ref_prefix) and item['parent_oid'] != target_channel_oid:
                    print(f'Moving {oid} into {target_channel_oid}')
                    msc.api('medias/edit/', method='post', data={'oid': oid, 'channel': f'mscid-{target_channel_oid}'})
        start = response['max_date']
        more = response['more']
