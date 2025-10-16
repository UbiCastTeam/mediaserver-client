#!/usr/bin/env python3
'''
Script to dump the entire catalog on legacy servers that to not support the catalog API
'''

import datetime
import argparse
import os
import sys
from pathlib import Path


def dump_oids_legacy(msc):
    oids = set()

    more = True
    start = (datetime.datetime.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')
    index = 0
    while more:
        print('//// Making request on latest (start=%s)' % start)
        response = msc.api(
            'latest/',
            params=dict(start=start, order_by='added', content='v', count=100),
        )
        for item in response['items']:
            index += 1
            oids.add(item["oid"])

        start = response['max_date']
        more = response['more']

    print(f"Found total of {len(oids)}")
    return oids


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument(
        '--conf',
        help='Path to the configuration file.',
        required=True,
        type=str,
    )
    parser.add_argument(
        '--file',
        default='oids.txt',
        help='Text file to store the list of oids into.',
        type=str,
    )

    args = parser.parse_args()
    msc = MediaServerClient(args.conf)

    version = msc.get_server_version()
    if version <= (12, 3, 0):
        oids = dump_oids_legacy(msc)
    else:
        oids = [v["oid"] for v in msc.get_catalog(fmt='json')["videos"]]

    print(f"Writing oids in to {args.file}")
    Path(args.file).open('w').write("\n".join(oids))
