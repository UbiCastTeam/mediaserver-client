#!/usr/bin/env python3
"""
Sript which aims at freeing storage by either
* deleting ABR (HLS) variants of unwatched media
* putting unwatched media to the trash
"""

import argparse
import os
import sys
import time

try:
    from ms_client.client import MediaServerClient, MediaServerRequestError
except ModuleNotFoundError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient, MediaServerRequestError


def get_human_readable_size(num: int, suffix: str = "B") -> str:
    """Return human-readable size with automatic suffix"""
    for unit in ("", "K", "M", "G", "T", "P"):
        if abs(num) < 1000:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1000
    return f"{num:.1f}Y{suffix}"


def filter_vod(media_list: list[dict]) -> list[dict]:
    """Filter list of dictionaries representing media that are VOD by looking at the oid"""
    return [v for v in media_list if v["object_id"][0] == "v"]


def media_is_deletable(resources: list[dict]) -> bool:
    """Determine if a media is deletable, i.e. if it uses a local or object storage manager"""
    for resource_obj in resources:
        manager = resource_obj.get("manager") or dict()
        if manager.get("service") in ["local", "object"]:
            return True


def query_deletable_unwatched_vods(msc: MediaServerClient, params: dict) -> list[dict]:
    """Use API to get unwatched media between dates, filter on deletable vod media, and
    finally query and insert resources information
    """
    print(f"Fetching unwatched media with options {params}")
    r = msc.api("/stats/unwatched/", params=params)

    # only look at VOD
    unwatched_vods = filter_vod(r.get("unwatched", []))

    unwatched_local_media = list()

    for index, vod in enumerate(unwatched_vods):
        print(f"Looking at VOD {index + 1}/{len(unwatched_vods)}", end="\r")
        oid = vod["object_id"]
        resources = msc.api("/medias/resources-list/", params={"oid": oid})["resources"]
        if media_is_deletable(resources):
            vod["resources"] = resources
            unwatched_local_media.append(vod)
    print()

    print(
        f"Found {len(unwatched_local_media)} unwatched VODs between {r['start_date']} and {r['end_date']}"
    )
    return unwatched_local_media


def get_total_size(vods: list[dict]) -> int:
    """Compute total size of VODs from list of dicts"""
    total_size = 0
    for vod in vods:
        total_size += vod["storage_used"]
    return total_size


def get_oids(medias: list[dict]) -> list[str]:
    """Produce list of oids from list of dicts"""
    return [m["object_id"] for m in medias]


def get_hls_resources(vods: list[dict]) -> [dict, int]:
    """Return list of hls resources indexed by oid, and total size of hls resources"""
    hls_resources = dict()
    hls_total_size = 0
    for index, vod in enumerate(vods):
        oid = vod["object_id"]
        for resource_obj in vod["resources"]:
            if resource_obj["format"] == "m3u8":
                hls_resources.setdefault(oid, [])
                hls_resources[oid].append(resource_obj["path"])
                hls_total_size += resource_obj["file_size"]
    return hls_resources, hls_total_size


def delete_hls_resources(
    msc: MediaServerClient, vods: list[dict], apply: bool = False
) -> int:
    """Delete or simulate deletion of list of hls resources, return deleted count"""
    hls_resources_to_delete, hls_size = get_hls_resources(vods)
    deleted_resources_count = 0
    if hls_size:
        print(
            f"Cleaning up {len(hls_resources_to_delete)} HLS resources will free "
            f"{get_human_readable_size(hls_size)}"
        )
        for oid, files in hls_resources_to_delete.items():
            if apply:
                print(f"Deleting resources of oid {oid}: {files}")
                params = {"oid": oid, "names": ",".join(files)}
                try:
                    r = msc.api("/medias/resources-delete/", method="post", data=params, timeout=180)
                except MediaServerRequestError as err:
                    if 'read timeout=' in str(err):
                        print(f'The deletion request timed out for "{oid}", this error can be ignored.')
                        deleted_resources_count += len(files)
                    else:
                        print(f"Error when deleting resources of {oid}: {r['message']}")
                else:
                    if not r["success"]:
                        print(f"Failure when deleting resources of {oid}: {r['message']}")
                    else:
                        deleted_resources_count += len(files)
            else:
                print(f"[Dry Run] Would delete resources of oid {oid}: {files}")
        if apply:
            print(f"Deleted {deleted_resources_count} resources")
        else:
            print(
                f"[Dry run] Could have freed up to {get_human_readable_size(hls_size)} by deleting HLS resources"
            )
    else:
        print("No HLS resources to cleanup")
    return deleted_resources_count


def delete_unwatched_vods(
    msc: MediaServerClient, vods: list[dict], apply: bool = False
) -> [int, str]:
    """Delete or simulate deletion of unwatched media, return deleted count and
    log file path which can be used to revert the operation using the mass_untrash script.
    Note that this function is really dangerous if the platform does not have the trash feature enabled
    """
    trashed_media_count = 0
    trashed_files_log_path = None
    media_size = get_total_size(vods)
    if media_size:
        media_to_delete_count = len(vods)
        print(
            f"Trashing {media_to_delete_count} unwatched VODs will free {get_human_readable_size(media_size)}"
        )
        oids = get_oids(vods)
        if apply:
            trashed_files_log_path = f"{time.strftime('%Y%m%d-%H%M%S')}-trashed.csv"
            print(f"Will put {media_to_delete_count} VODs to trash")
            deleted_statuses = msc.api(
                "/catalog/bulk_delete/", method="post", data={"oids": oids}
            )["statuses"]

            trashed_media_count = 0
            for object_id, status in deleted_statuses.items():
                if status["status"] == 200:
                    trashed_media_count += 1
                else:
                    print(
                        f"Media {object_id} could not be deleted: {status.get('message')}"
                    )

            with open(trashed_files_log_path, "w") as f:
                print(f"Writing list of deleted oids to {trashed_files_log_path}")
                f.write("\n".join(oids))
            print(
                f"Trashed {trashed_media_count} VODs, freed up to {get_human_readable_size(media_size)}"
            )
        else:
            print(f"[Dry Run] Would delete {media_to_delete_count} VODs: {oids}")
            print(
                f"Trashing these VODs would have freed up to {get_human_readable_size(media_size)}"
            )
    else:
        print("No VOD to trash")
    return trashed_media_count, trashed_files_log_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--conf",
        help="Path to the configuration file (e.g. myconfig.json).",
        required=True,
        type=str,
    )

    parser.add_argument(
        "--start-date",
        help="Start date (e.g. 2023-10-25). Both start date and end date must be specified.",
        type=str,
        default="2007-10-10",
    )

    parser.add_argument(
        "--end-date",
        help="End date (e.g. 2023-10-30). Both start date and end date must be specified.",
        type=str,
        required=True,
    )

    parser.add_argument(
        "--action",
        help="Action to run on unwatched media; note if trash is selected, the oid list will be written into a file",
        choices=["reduce_size", "trash"],
        required=True,
    )

    parser.add_argument(
        "--apply",
        help="Whether to apply changes or not",
        action="store_true",
    )

    parser.add_argument(
        "--max-views",
        help="Number of views over the period to consider unwatched",
        required=False,
        type=int,
        default=0,
    )

    parser.add_argument(
        "--channel-oid",
        help="Root channel oid; if unspecified, will process the entire catalog.",
        type=str,
    )

    args = parser.parse_args()

    msc = MediaServerClient(args.conf)

    params = dict()

    if args.start_date and args.end_date:
        params["sd"] = args.start_date
        params["ed"] = args.end_date

    if args.channel_oid:
        params["oid"] = args.channel_oid
        params["recursive"] = "yes"

    params["views_threshold"] = args.max_views

    vods = query_deletable_unwatched_vods(msc, params)

    action = args.action
    if action == "reduce_size":
        delete_hls_resources(msc, vods, apply=args.apply)
    elif action == "trash":
        yesno = input(
            "WARNING: TRIPLE CHECK THAT YOUR PLATFORM HAS THE TRASH ENABLED "
            f"here {msc.conf['SERVER_URL']}/admin/settings/#id_trash_enabled (type 'yes')"
        )
        if yesno.lower() != "yes":
            sys.exit()
        delete_unwatched_vods(msc, vods, apply=args.apply)
