#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to ping a MediaServer.
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
