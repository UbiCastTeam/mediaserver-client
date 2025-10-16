#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to ping a MediaServer.
'''
import argparse
import os
import sys
from datetime import datetime
import time


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient
    from ms_client.lib.utils import TTYColors as C

    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument(
        'conf',
        default=None,
        help='The configuration to use.',
        nargs='?',
        type=str,
    )
    args = parser.parse_args()

    msc = MediaServerClient(args.conf)

    # ping
    while True:
        begin = datetime.now()
        before = time.time()
        print(f'{begin} ping')
        url = f'/?usage=mytest&ts={before}'
        print(msc.api(url, timeout=2))
        took = int(1000 * (time.time() - before))
        color = C.RESET
        if took > 3000:
            color = C.RED
        elif took > 500:
            color = C.YELLOW
        print(f'{color}{url} took {took} ms{C.RESET}')
