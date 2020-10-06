#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to upload videos

./examples/upload.py --config beta.json --input test.mp4 --title "mytitle" --channel "mscpath-A/B/C" --speaker-email "test@test.com"
'''
import argparse
import logging
import os
import sys

logger = logging.getLogger('upload_speed_test')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to file to upload'
    )

    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to config file.'
    )

    parser.add_argument(
        '--channel',
        type=str,
        required=False,
        help='Channel to publish to (can be mscspeaker, mscpath-A/B/C, mscid-1234, or just a title string).'
    )

    parser.add_argument(
        '--speaker-email',
        type=str,
        required=False,
        help='Speaker email; should be set if channel is "mscspeaker".'
    )

    parser.add_argument(
        '--title',
        type=str,
        required=False,
        help='Media title',
    )

    args = parser.parse_args()

    # get ms client
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    def print_progress(progress):
        print(f'Uploading: {progress * 100:.1f}%')

    msc = MediaServerClient(args.config)
    msc.check_server()
    resp = msc.add_media(
        file_path=args.input,
        title=args.title,
        channel=args.channel,
        speaker_email=args.speaker_email,
        progress_callback=print_progress,
    )
    if resp['success']:
        print(f'File {args.input} upload finished, object id is {resp["oid"]}')
    else:
        print(f'Upload of {args.input} failed: {resp}')
