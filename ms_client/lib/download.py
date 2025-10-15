"""
MediaServer client download library
This module is not intended to be used directly, only the client class should be used.
"""
from __future__ import annotations

import logging
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import unidecode

from .utils import bytes_repr, item_repr
if TYPE_CHECKING:
    from ..client import MediaServerClient

logger = logging.getLogger(__name__)


def get_prefix(item: dict) -> str:
    return unidecode.unidecode((item.get('title', '')[:57]).replace('/', '|').strip(' -') + ' - ') + item['oid']


def download_media_metadata_zip(
    client: MediaServerClient,
    media_item: dict,
    dir_path: Path | str,
    file_prefix: str | None = None,
    current_size: int | None = None,
    include_annotations: Literal['all', 'editorial', 'none'] = 'all',
    include_resources_links: Literal['yes', 'no'] = 'yes',
    timeout: int | None = 3600,
    max_retry: int | None = None
) -> Path | None:
    """
    Download the metadata ZIP file of a media.
    The `current_size` parameter can be used to skip the download if the file exists and has the same size.
    Use `None` to get the size of the desctination file if it exist. Use `0` to always download the file.
    """
    if not media_item.get('oid'):
        raise ValueError('You should give an object id to get the zip file.')

    logger.info('Downloading metadata for media %s.', item_repr(media_item))

    valid_annotations = ('all', 'editorial', 'none')
    if include_annotations not in valid_annotations:
        raise ValueError(f'Invalid value given for "include_annotations". Valid values: {valid_annotations}.')
    valid_resources = ('yes', 'no')
    if include_resources_links not in valid_resources:
        raise ValueError(f'Invalid value given for "include_resources_links". Valid values: {valid_resources}.')

    params = {
        'oid': media_item['oid'],
        'annotations': include_annotations,
        'resources': include_resources_links
    }

    version = client.get_server_version()
    url = 'download/metadata/' if version >= (13, 2, 0) else 'medias/get/zip/'

    dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    if not file_prefix:
        file_prefix = get_prefix(media_item)
    path = dir_path / f'{file_prefix}.zip'

    if current_size is None and path.is_file():
        current_size = path.stat().st_size

    if current_size:
        req = client.api(
            url,
            method='head',
            params=params,
            timeout=timeout,
            max_retry=max_retry
        )
        try:
            size = int(req.headers.get('Content-Length'))
            assert size > 0
        except (ValueError, TypeError, AssertionError) as err:
            logger.warning('Failed to get expected size of %s: %s', media_item['oid'], err)
        if current_size == size:
            logger.info(
                'Skipping download of "%s" because the file already exists and has the expected size.',
                path.name
            )
            return None

    begin = time.time()
    req = client.api(
        url,
        method='get',
        params=params,
        timeout=timeout,
        max_retry=max_retry,
        stream=True
    )
    total_size = 0
    with open(path, 'wb') as fo:
        for chunk in req.iter_content(client.conf['DOWNLOAD_CHUNK_SIZE']):
            fo.write(chunk)
            total_size += len(chunk)
    bandwidth = total_size / (time.time() - begin)
    logger.info(f'Download finished, average bandwidth was {bytes_repr(bandwidth)}/s.')

    # Check that the zip file is valid
    with zipfile.ZipFile(path, 'r') as zf:
        files_with_error = zf.testzip()
        if files_with_error:
            raise RuntimeError(f'Some files have errors in the zip file: {files_with_error}')
    return path


def download_media_best_resource(
    client: MediaServerClient,
    media_item: dict,
    dir_path: Path | str,
    file_prefix: str | None = None,
    current_size: int | None = None,
    should_be_playable: bool = False,
    timeout: int | None = 3600,
    max_retry: int | None = None
) -> Path | None:
    """
    Download the best audio/video resource file of a media.
    The `current_size` parameter can be used to skip the download if the file exists and has the same size.
    Use `None` to get the size of the desctination file if it exist. Use `0` to always download the file.
    """
    if not media_item.get('oid'):
        raise ValueError('You should give an object id to download a resource file.')

    if media_item['oid'][0] != 'v':
        logger.info('The media %s is not a video, skipping resource download.', media_item['oid'])
        return None

    logger.info('Downloading resource for media %s.', item_repr(media_item))

    resources = client.api('medias/resources-list/', params=dict(oid=media_item['oid']))['resources']
    if not resources:
        logger.info('The media %s has no resource.', media_item['oid'])
        return None

    best_quality = None
    resources.sort(key=lambda a: -a['file_size'])
    for res in resources:
        if res['format'] != 'm3u8' and (not should_be_playable or res['used_for_display']):
            best_quality = res
            break
    if not best_quality:
        logger.warning('No resource file can be downloaded for video %s. Resources: %s.', media_item['oid'], resources)
        raise RuntimeError(f'Could not download any resource from list: {resources}.')
    logger.info('Best quality file for video %s: %s', media_item['oid'], best_quality['file'])

    dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)
    if not file_prefix:
        file_prefix = get_prefix(media_item)
    path = dir_path / f'{file_prefix}-{best_quality["width"]}x{best_quality["height"]}.{best_quality["format"]}'

    if current_size is None and path.is_file():
        current_size = path.stat().st_size

    if best_quality['format'] in ('youtube', 'embed'):
        # Dump youtube video id or embed code to a file
        data = best_quality['file'].encode('utf-8')
        size = len(data)
        if current_size and current_size == size:
            logger.info(
                'Skipping download of "%s" because the file already exists and has the expected size.',
                path.name
            )
            return None

        path.write_bytes(data)
        return path

    # Download resource
    url = client.api(
        'download/',
        params=dict(oid=media_item['oid'], url=best_quality['path'], redirect='no')
    )['url']

    if current_size:
        req = client.api(
            url,
            method='head',
            authenticate=False,
            timeout=timeout,
            max_retry=max_retry
        )
        try:
            size = int(req.headers.get('Content-Length'))
            assert size > 0
        except (ValueError, TypeError, AssertionError) as err:
            logger.warning('Failed to get expected size of %s: %s', media_item['oid'], err)
        if current_size == size:
            logger.info(
                'Skipping download of "%s" because the file already exists and has the expected size.',
                path.name
            )
            return None

    begin = time.time()
    req = client.api(
        url,
        method='get',
        authenticate=False,
        timeout=timeout,
        max_retry=max_retry,
        stream=True
    )
    total_size = 0
    with open(path, 'wb') as fo:
        for chunk in req.iter_content(client.conf['DOWNLOAD_CHUNK_SIZE']):
            fo.write(chunk)
            total_size += len(chunk)
    bandwidth = total_size / (time.time() - begin)
    logger.info(f'Download finished, average bandwidth was {bytes_repr(bandwidth)}/s.')

    return path


def backup_media(
    client: MediaServerClient,
    media_item: dict,
    dir_path: Path | str,
    should_be_playable: bool = False,
    replicate_tree: bool = False
) -> Path:
    if not media_item.get('oid'):
        raise ValueError('You should give an object id to get the zip file.')

    logger.info('Backuping media %s.', item_repr(media_item))

    channels = client.api('channels/path/', params=dict(oid=media_item['oid']))['path']
    media_chan_path = [channel['title'].replace('/', '|') for channel in channels]
    if replicate_tree:
        media_backup_dir = Path(dir_path, *[get_prefix(channel) for channel in channels])
    else:
        media_backup_dir = Path(dir_path)
    media_backup_dir.mkdir(parents=True, exist_ok=True)

    file_prefix = get_prefix(media_item)
    zip_path = media_backup_dir / f'{file_prefix}.zip'
    metadata_zip_size = 0
    best_resource_size = 0
    if zip_path.is_file():
        # Get file size from existing zip to skip downloads if useless
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            for name in zip_file.namelist():
                if name == 'metadata-size.txt':
                    metadata_zip_size = int(zip_file.open(name).read())
                elif name.startswith('resource-'):
                    file_info = zip_file.getinfo(name)
                    best_resource_size = file_info.file_size
        logger.info(
            'The backup archive "%s" already exists (metadata size: %s B, resource size: %s B).',
            zip_path.name, metadata_zip_size, best_resource_size
        )

    tmp_prefix = f'tmp-{media_item["oid"]}'
    meta_path = download_media_metadata_zip(
        client=client,
        media_item=media_item,
        dir_path=media_backup_dir,
        file_prefix=tmp_prefix,
        current_size=metadata_zip_size,
        include_resources_links='no'
    )
    res_path = download_media_best_resource(
        client=client,
        media_item=media_item,
        dir_path=media_backup_dir,
        file_prefix=tmp_prefix,
        current_size=0 if meta_path else best_resource_size,
        should_be_playable=should_be_playable
    )
    if res_path and not meta_path:
        # Force zip download if the best resource has changed and if the metadata were not already downloaded
        meta_path = download_media_metadata_zip(
            client=client,
            media_item=media_item,
            dir_path=media_backup_dir,
            file_prefix=tmp_prefix,
            current_size=0,
            include_resources_links='no'
        )

    if res_path or meta_path:
        # The metadata or the best resource has changed, put resource in zip and update info
        if not meta_path:
            raise RuntimeError('The metadata and the resource should have been downloaded.')
        metadata_size = meta_path.stat().st_size

        # Add resource and some other informations in the zip file
        with zipfile.ZipFile(meta_path, 'a') as zf:
            zf.writestr('metadata-size.txt', str(metadata_size))
            zf.writestr('metadata-path.txt', '/'.join(media_chan_path))
            if res_path:
                zf.write(res_path, 'resource' + res_path.name.removeprefix(tmp_prefix))

        # CRC check of the zip file
        with zipfile.ZipFile(meta_path, 'r') as zf:
            files_with_error = zf.testzip()
            if files_with_error:
                raise RuntimeError(f'Some files have errors in the zip file: {files_with_error}')

        # Rename zip file and remove temporary files
        meta_path.rename(zip_path)
        if res_path:
            res_path.unlink(missing_ok=True)

        logger.info(
            'The backup archive "%s" has been created.',
            zip_path.name
        )
    else:
        logger.info(
            'The backup archive "%s" was already existing and has expected size.',
            zip_path.name
        )

    return zip_path
