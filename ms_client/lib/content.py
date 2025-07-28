"""
MediaServer client content library
This module is not intended to be used directly, only the client class should be used.
"""
from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Callable
if TYPE_CHECKING:
    from ..client import MediaServerClient

logger = logging.getLogger(__name__)


def add_media(
    client: MediaServerClient,
    title: str | None = None,
    file_path: Path | str | None = None,
    progress_callback: Callable | None = None,
    progress_data: dict | None = None,
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
            progress_data=progress_data,
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


def download_metadata_zip(
    client: MediaServerClient,
    media_oid: str,
    path: Path | str,
    include_annotations: Literal['all', 'editorial', 'none'] = 'none',
    include_resources_links: Literal['yes', 'no'] = 'no',
    force: bool = False,
    timeout: int | None = 3600,
    max_retry: int | None = None
) -> Path:
    if not media_oid:
        raise ValueError('You should give an object id to get the zip file.')
    valid_annotations = ('all', 'editorial', 'none')
    if include_annotations not in valid_annotations:
        raise ValueError(f'Invalid value given for "include_annotations". Valid values: {valid_annotations}.')
    valid_resources = ('yes', 'no')
    if include_resources_links not in valid_resources:
        raise ValueError(f'Invalid value given for "include_resources_links". Valid values: {valid_resources}.')
    params = dict(
        oid=media_oid,
        annotations=include_annotations,
        resources=include_resources_links
    )
    path = Path(path)
    if not force and path.is_file():
        size = path.stat().st_size
        req = client.api(
            'medias/get/zip/',
            method='head',
            params=params,
            timeout=timeout,
            max_retry=max_retry
        )
        if req.headers.get('Content-Length') == str(size):
            logger.info(
                'Skipping download of zip file for %s because the file already exists and has the correct size.',
                media_oid
            )
            return path
    req = client.api(
        'medias/get/zip/',
        method='get',
        params=params,
        timeout=timeout,
        max_retry=max_retry,
        stream=True
    )
    with open(path, 'wb') as fo:
        for chunk in req.iter_content(10000000):  # 10 MB chunks
            fo.write(chunk)

    # Check that the file is really a zip file
    zip_file = zipfile.ZipFile(path, 'r')
    if zip_file.testzip():
        raise Exception('Invalid zip file')
    return path


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
