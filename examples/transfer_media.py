#!/usr/bin/env python3
"""
Script to move one media from one video platform to another

Usage:
./transfer_media.py --conf-src ../configs/src.json --conf-dest ../configs/dest.json --oid v12689655a7a850wrgs8 --delete
"""

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

import requests


def download_file(url, local_filename, verify=True):
    with requests.get(url, stream=True, verify=verify) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length"))
        downloaded_size = 0
        with open(local_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                downloaded_size += len(chunk)
                print(
                    f"Downloading {(100 * downloaded_size / total_size):.1f}%", end="\r"
                )
                f.write(chunk)
    return local_filename


def backup_media(msc, oid, temp_path):
    if not oid.startswith("v"):
        raise Exception(f"oid {oid} is not a VOD")

    finished_marker = temp_path / "finished.marker"
    if finished_marker.is_file():
        print(f"Skipping {temp_path} download: already done")
        return Path(finished_marker.open().read())

    media_download_dir.mkdir(parents=True)
    item = msc.api("medias/get/", params={"oid": oid})["info"]
    meta_path = download_media_metadata(msc, item, temp_path, oid)
    res_path = download_media_best_resource(msc, item, temp_path, oid)

    zip_file = zipfile.ZipFile(meta_path, "a")
    print(f"Embedding {res_path} into {meta_path}")
    zip_file.write(res_path, os.path.basename(res_path))
    zip_file.close()

    finished_marker.open("w").write(meta_path)
    print(f"media {oid} downloaded to {meta_path}")
    return meta_path


def download_media_best_resource(msc, item, media_download_dir, file_prefix):
    resources = msc.api("medias/resources-list/", params=dict(oid=item["oid"]))[
        "resources"
    ]
    resources.sort(key=lambda a: -a["file_size"])
    if not resources:
        print("Media has no resources.")
        return
    best_quality = None
    for r in resources:
        if r["format"] != "m3u8":
            best_quality = r
            break
    if not best_quality:
        raise Exception(f"Could not download any resource from list: {resources}")

    print(f"Best quality file for video {item['oid']}: {best_quality['file']}")
    destination_resource = os.path.join(
        media_download_dir,
        "resource - %s - %sx%s.%s"
        % (
            file_prefix,
            best_quality["width"],
            best_quality["height"],
            best_quality["format"],
        ),
    )

    if best_quality["format"] in ("youtube", "embed"):
        # dump youtube video id or embed code to a file
        with open(destination_resource, "w") as fo:
            fo.write(best_quality["file"])
    else:
        # download resource
        resource_url = msc.api(
            "download/",
            params=dict(oid=item["oid"], url=best_quality["file"], redirect="no"),
        )["url"]

        print(f"Will download file to '{destination_resource}'.")
        download_file(resource_url, destination_resource)
    return destination_resource


def download_media_metadata(msc, item, media_download_dir, file_prefix):
    metadata_zip_path = media_download_dir / f"{file_prefix}.zip"
    path = msc.download_metadata_zip(
        item["oid"],
        metadata_zip_path,
        include_annotations="all",
        include_resources_links="no",
    )
    print(f"Metadata downloaded for media {item['oid']}: '{path}'.")
    return str(path)


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(description=__doc__.strip())

    parser.add_argument(
        "--conf-src",
        help="Path to the configuration file for the source platform.",
        required=True,
        type=str,
    )

    parser.add_argument(
        "--conf-dest",
        help="Path to the configuration file for the destination platform.",
        required=True,
        type=str,
    )

    parser.add_argument(
        "--temp-path",
        help="Temporary folder to use.",
        default=Path("temp"),
        type=Path,
    )

    parser.add_argument(
        "--oid",
        help="oid of the media to transfer, can be used multiple times",
        type=str,
        action='append',
    )

    parser.add_argument(
        "--oid-file",
        help="Path to file containing one oid per line",
        type=Path,
    )

    parser.add_argument(
        "--redirections-file",
        help="Path to file containing the previous oid and the new oid on each line",
        default=Path("redirections.csv"),
        type=Path,
    )

    parser.add_argument(
        "--root-channel", help="Optional root channel to move media into", type=str
    )

    parser.add_argument(
        "--delete-temp",
        help="Whether to keep the downloaded folder",
        action="store_true",
    )

    parser.add_argument(
        "--apply",
        help="Whether to apply changes",
        action="store_true",
    )

    args = parser.parse_args()

    msc_src = MediaServerClient(args.conf_src)
    msc_dest = MediaServerClient(args.conf_dest)

    oids = list()
    if args.oid_file and args.oid_file.is_file():
        print(f"Reading oids from {args.oid_file}")
        oids = args.oid_file.open().read().strip().split('\n')
    if args.oid:
        oids += args.oid

    oid_count = len(oids)
    if oid_count:
        print(f"Found {oid_count} oids to transfer")
    else:
        sys.exit("No oids provided, exiting")

    for index, oid in enumerate(oids):
        print(f"Processing {index + 1}/{oid_count}")
        media_download_dir = args.temp_path / oid
        zip_path = backup_media(msc_src, oid, media_download_dir)

        def print_progress(progress):
            print(f"Uploading: {progress * 100:.1f}%", end="\r")

        if args.apply:
            print("Starting upload")
            resp = msc_dest.add_media(
                file_path=zip_path, progress_callback=print_progress
            )

            if resp["success"]:
                print(f"File {zip_path} upload finished, object id is {resp['oid']}")
            else:
                print(f"Upload of {zip_path} failed: {resp}")
        else:
            print(f"[Dry run] Would upload {zip_path}")

        if args.delete_temp and media_download_dir.exists():
            print(f"Deleting {media_download_dir}")
            shutil.rmtree(media_download_dir)
