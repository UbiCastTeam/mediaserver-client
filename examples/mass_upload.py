#!/usr/bin/env python3
'''
Script to upload all videos contained in a folder

./examples/mass_upload.py \
    --config beta.json --input myfolder --channel "mscpath-A/B/C"
'''
from pathlib import Path

import argparse
import logging
import os
import sys

logger = logging.getLogger('mass_upload')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__.strip(),
    )

    parser.add_argument(
        '--folder',
        type=str,
        required=True,
        help='Path to folder to upload (not recursive)',
    )

    parser.add_argument(
        '--config', type=str, required=True, help='Path to config file.'
    )

    parser.add_argument(
        '--channel',
        type=str,
        required=True,
        help='Channel to publish all files into (can be mscspeaker, mscpath-A/B/C, mscid-1234, ...)',
    )

    parser.add_argument(
        '--speaker-email',
        type=str,
        required=False,
        help='Speaker email; should be set if channel is "mscspeaker".',
    )

    args = parser.parse_args()

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    def print_progress(progress):
        print(f'Uploading: {progress * 100:.1f}%')

    msc = MediaServerClient(args.config)
    folder = Path(args.folder)
    for node in folder.glob("*.*"):
        if node.is_file():
            resp = msc.add_media(
                file_path=str(node),
                channel=args.channel,
                speaker_email=args.speaker_email,
                progress_callback=print_progress,
            )
        if resp['success']:
            print(f'File {node} upload finished, object id is {resp["oid"]}')
        else:
            print(f'Upload of {node} failed: {resp}')
