#!/usr/bin/env python3
'''
Script to dump all users with an email and with data in their personal channel into a CSV file
'''
import os
import sys
import csv


if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient

    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    users = msc.api('/users/', params={"limit": 0})["users"]
    print(f"Found {len(users)} users")

    users_with_data = list()

    for user in users:
        user_id = user["id"]
        try:
            oid = msc.api(
                '/channels/personal/', params={"create": "no", "id": user_id}
            )["oid"]
            size = msc.api('/channels/get/', params={"oid": oid, "full": "yes"})[
                "info"
            ]["storage_used"]
            if size > 0 and user.get("email"):
                users_with_data.append(user)
        except Exception as e:
            if "403" in str(e):
                pass

    csv_path = "users_with_data.csv"
    print(f"Found {len(users_with_data)} users with data, writing to {csv_path}")

    if len(users_with_data):
        with open(csv_path, "w") as csvfile:
            fieldnames = ["email", "first_name", "last_name"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for user in users_with_data:
                user_simple = dict()
                for key, value in user.items():
                    if key in fieldnames:
                        user_simple[key] = value
                writer.writerow(user_simple)
