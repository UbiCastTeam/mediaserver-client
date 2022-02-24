#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Script to upload videos

./examples/upload.py --config mynudgis.json --input test.mp4 --title "mytitle" --channel "mscpath-A/B/C" --speaker-email "test@test.com"
'''
import argparse
from urllib.parse import urlparse
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
        help='Path to file to upload, or HTTP URL of media file to import'
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

    params = {
        'title': args.title,
        'channel': args.channel,
        'speaker_email': args.speaker_email,
        'progress_callback': print_progress,
    }

    # depending on the case (local or remote file) the API argument is not the same
    input_arg = None
    if os.path.isfile(args.input):
        input_arg = 'file_path'
    else:
        u = urlparse(args.input)
        if u.scheme and 'http' in u.scheme:
            input_arg = 'file_url'
            # we do not need to specify a title in case of file upload because the
            # client will use the filename as fallback, but it is not supported for URLs
            params['title'] = u.path.split('/')[-1]

    if input_arg is None:
        print(f'Unkown or unsupported input {args.input}')
        sys.exit(1)

    params[input_arg] = args.input

    resp = msc.add_media(**params)

    if resp['success']:
        print(f'File {args.input} upload finished, object id is {resp["oid"]} and can be accessed at {msc.conf["SERVER_URL"]}/permalink/{resp["oid"]}')
    else:
        print(f'Upload of {args.input} failed: {resp}')
