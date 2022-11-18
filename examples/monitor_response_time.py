#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to ping a MediaServer.
'''
import os
import sys
from datetime import datetime
import time


RED = '\033[91m'
YELLOW = '\033[93m'
DEFAULT = '\033[0m'


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    while True:
        begin = datetime.now()
        before = time.time()
        print(f'{begin} ping')
        url = f'/?usage=mytest&ts={before}'
        print(msc.api(url, timeout=2))
        took = int(1000 * (time.time() - before))
        color = DEFAULT
        if took > 3000:
            color = RED
        elif took > 500:
            color = YELLOW
        print(f'{color}{url} took {took} ms{DEFAULT}')
