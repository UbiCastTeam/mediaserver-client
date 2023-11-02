#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to generate a CSV file for metadata from all media in the database
"""
import os
import sys


def generate_csv(msc, csv_path):
    with open(csv_path, "w") as f:
        print("Fetching catalog")
        catalog_csv = msc.api(
            "catalog/get-all/", params={"format": "csv"}, parse_json=False, timeout=30,
        )
        print(f"Writing {csv_path}")
        f.write(catalog_csv)


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    msc.check_server()

    csv_path = f'media-{msc.conf["SERVER_URL"].split("://")[1]}.csv'
    if os.path.isfile(csv_path):
        print(f"File {csv_path} already exists, exiting with error")
        sys.exit(1)

    generate_csv(msc, csv_path)
    print(f"Finished writing {csv_path}")
