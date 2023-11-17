#!/usr/bin/env python3
import argparse
import os
import sys


def get_media_by_speaker_email(msc, csv_path, target_speaker_email):
    media_by_speaker = dict()
    print("Fetching catalog")
    catalog = msc.api(
        "catalog/get-all/",
        params={"format": "flat"},
        timeout=30,
    )
    videos = catalog["videos"]
    for video in videos:
        oid = video["oid"]
        speaker_emails = video["speaker_email"].split(" | ")
        for speaker_email in speaker_emails:
            media_by_speaker.setdefault(speaker_email, [])
            media_by_speaker[speaker_email].append(oid)
    oids = media_by_speaker.get(target_speaker_email)
    if oids:
        print(f"Found {len(oids)} videos for email {target_speaker_email}")
        with open(csv_path, "w") as f:
            f.write("\n".join(oids))
            print(f"Finished writing {csv_path}")
    else:
        print(f"No video found for email {target_speaker_email}")


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(
        description=(
            "Look for all media containing a specific email address in the speaker_email field, "
            "write one matching oid by line in a CSV file named after the target email (note that "
            "it will be overwritten without warning); WARNING: this is rate-limited, use with parcimony."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--conf",
        help="Path to the configuration file (e.g. myconfig.json).",
        required=True,
        type=str,
    )

    parser.add_argument(
        "--target-email",
        help="Speaker email to look for",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)

    args = parser.parse_args()
    msc = MediaServerClient(args.conf)

    speaker_email = args.target_email
    csv_path = f'media-{speaker_email.replace("@", "AT")}.csv'

    get_media_by_speaker_email(msc, csv_path, speaker_email)
