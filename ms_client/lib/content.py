"""
MediaServer client content library
This module is not intended to be used directly, only the client class should be used.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Callable

if TYPE_CHECKING:
    from ..client import MediaServerClient

logger = logging.getLogger(__name__)


def add_media(
    client: MediaServerClient,
    title: str | None = None,
    file_path: Path | str | None = None,
    progress_callback: Callable[[float], None] | None = None,
    timeout: int | None = 3600,
    max_retry: int | None = None,
    **metadata
) -> dict:
    if not title and not file_path:
        raise ValueError('You should give a title or a file to create a media.')
    if file_path is not None:
        file_path = Path(file_path)
        if file_path.stat().st_size == 0:
            raise ValueError('File is empty: %s' % file_path)
    metadata['origin'] = client.conf['CLIENT_ID']
    if title:
        metadata['title'] = title
    if file_path:
        upload_retry = max_retry if max_retry is not None else 10
        metadata['code'] = client.chunked_upload(
            file_path,
            progress_callback=progress_callback,
            max_retry=upload_retry
        )
    response = client.api(
        'medias/add/',
        method='post',
        data=metadata,
        timeout=timeout,
        max_retry=max_retry
    )
    return response


def remove_all_content(
    client: MediaServerClient,
    timeout: int | None = None,
    max_retry: int | None = None,
) -> None:
    logger.info('Remove all content')
    channels = client.api('channels/tree/')['channels']
    while client.api('channels/tree')['channels']:
        for c in channels:
            c_oid = c['oid']
            client.api(
                'channels/delete/',
                method='post',
                data={'oid': c_oid, 'delete_content': 'yes'},
                timeout=timeout,
                max_retry=max_retry
            )
            logger.info('Emptied channel %s', c_oid)
        channels = client.api('channels/tree/')['channels']


def get_catalog(
    client: MediaServerClient,
    fmt: Literal['flat', 'tree', 'csv'] = 'flat',
    timeout: int | None = 120
) -> dict | str:
    version = client.get_server_version()
    if version >= (12, 3, 0):
        as_tree = (fmt == 'tree')
        api_fmt = 'csv' if fmt == 'csv' else 'json'
        catalog = client.api(
            'catalog/get-all/',
            params={'format': api_fmt},
            parse_json=(api_fmt == 'json'),
            timeout=timeout
        )
        if as_tree:
            channels = {channel['oid']: channel for channel in catalog['channels']}
            tree = {'channels': []}
            for model_type, objects in catalog.items():
                for obj in objects:
                    parent_oid = obj['parent_oid']
                    if model_type == 'channels' and parent_oid is None:
                        tree['channels'].append(obj)
                    else:
                        channels[parent_oid].setdefault(model_type, []).append(obj)
            return tree
        else:
            return catalog
    else:
        return client.api(
            'catalog/get-all/',
            params={'format': fmt},
            parse_json=(fmt != 'csv'),
            timeout=timeout
        )
