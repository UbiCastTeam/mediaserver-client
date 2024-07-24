#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to generate a JSON file for metadata from all media in the database. The primary nodes are channels.
"""
import os
import sys
import json


def generate_json(msc, json_path):
    with open(json_path, "wb") as f:
        print("Fetching catalog as a JSON file")
        catalog_json = msc.get_catalog(fmt='tree')
        print(f"Writing {json_path}")
        f.write(json.dumps(catalog_json).encode('utf-8'))


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    json_path = f'media-{msc.conf["SERVER_URL"].split("://")[1]}.json'
    if os.path.isfile(json_path):
        print(f"File {json_path} already exists, exiting with error")
        sys.exit(1)

    generate_json(msc, json_path)
    print(f"Finished writing {json_path}")
