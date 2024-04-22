#!/usr/bin/env python3
import argparse
import os
import sys


def get_media_by_speaker_email(msc, csv_path, target_speaker_email):
    print('Fetching results')
    search_results = msc.api(
        'search/',
        params={
            'search': target_speaker_email,
            'content': 'v',
            'order_by': 'default',
            'fields': 'speaker',
        },
        timeout=30,
    )
    videos = search_results['videos']
    if videos:
        print(f'Found {len(videos)} videos for email {target_speaker_email}')
        with open(csv_path, 'w') as f:
            f.write('\n'.join([video['oid'] for video in videos]))
            print(f'Finished writing {csv_path}')
    else:
        print(f'No video found for email {target_speaker_email}')


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(
        description=(
            'Look for all media containing a specific email address in the speaker_email field, '
            'write one matching oid by line in a CSV file named after the target email (note that '
            'it will be overwritten without warning); WARNING: this is rate-limited, use with parcimony.'
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        '--conf',
        help='Path to the configuration file (e.g. myconfig.json).',
        required=True,
        type=str,
    )

    parser.add_argument(
        '--target-email',
        help='Speaker email to look for',
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
