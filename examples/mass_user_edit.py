#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Mass edit users targeted by email from a CSV file (first column by default)

This example script disables storage quota, edit the "data" dict to change the effect

'''
import os
import sys
import argparse


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '--conf',
        help='Path to the configuration file.',
        required=True,
        type=str
    )

    parser.add_argument(
        '--csv',
        help='Path to CSV file; the column expected to be the user email \
                is defined by the --column option. Lines starting with "#" will be ignored',
        required=True,
        type=str
    )

    parser.add_argument(
        '--column',
        help='Column count where the oid should be expected',
        default=0,
        type=int
    )

    parser.add_argument(
        '--csv-separator',
        help='CSV separator',
        default='\t',
        type=str
    )

    args = parser.parse_args()

    msc = MediaServerClient(args.conf)
    # ping
    print(msc.api('/'))

    with open(args.csv, 'r') as f:
        csv_data = f.read().strip()
        count = 0
        freed = 0
        lines = [line for line in csv_data.split('\n') if (line and not line.startswith('#'))]
        total_lines = len(lines)
        print(f'About to edit {total_lines} users')

        for index, line in enumerate(lines):
            user_email = line.split(args.csv_separator)[args.column]
            if user_email:
                # Possible data: username, email, password, is_active, emails_lang, company, position,
                # country, street, city, zip_code, first_name, last_name, receive_subscription_emails,
                # receive_support_end_emails, receive_max_viewers_emails, receive_available_storage_emails,
                # speaker_id, shared, storage_quota.
                data = {'email': user_email, 'storage_quota': 0}
                try:
                    print(f'[{index + 1}/{total_lines}] About to edit {user_email}')
                    msc.api('users/edit/', method='post', data=data)
                    count += 1
                except Exception as e:
                    print(f'Error on {user_email}: {e}')
        print(f'Edited {count} users')
