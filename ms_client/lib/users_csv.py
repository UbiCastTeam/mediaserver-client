"""
MediaServer client csv library
This module is not intended to be used directly, only the client class should be used.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import MediaServerClient

logger = logging.getLogger(__name__)


def import_users_csv(
    client: MediaServerClient,
    csv_path: Path | str,
    timeout: int | None = None,
    max_retry: int | None = None
) -> None:
    group_name = f'Users imported from csv on {time.ctime()}'
    group_id = client.api(
        'groups/add/',
        method='post',
        data={'name': group_name}
    ).get('id')
    logger.info(f'Created group {group_name} with id {group_id}')
    path = Path(csv_path)
    content = path.read_text()
    for index, line in enumerate(content.split('\n')):
        # Skip first line (contains header)
        if line and index > 0:
            fields = [field.strip() for field in line.split(';')]
            email = fields[2]
            user = {
                'email': email,
                'first_name': fields[0],
                'last_name': fields[1],
                'company': fields[3],
                'username': email,
                'is_active': 'true',
            }
            logger.info(f'Adding user "{email}"')
            try:
                response = client.api(
                    'users/add/',
                    method='post',
                    data=user,
                    timeout=timeout,
                    max_retry=max_retry
                )
            except Exception as err:
                logger.error(f'Error: {err}')
            else:
                logger.info(f'Success: {response}')
            logger.info(f'Adding user "{email}" to group "{group_name}"')
            try:
                response = client.api(
                    'groups/members/add/',
                    method='post',
                    data={'id': group_id, 'user_email': email},
                    timeout=timeout,
                    max_retry=max_retry
                )
            except Exception as err:
                logger.error(f'Error: {err}')
            else:
                logger.info(f'Success: {response}')
