"""
MediaServer client upload library
This module is not intended to be used directly, only the client class should be used.
"""
from __future__ import annotations

import logging
import math
import time
import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .utils import bytes_repr
if TYPE_CHECKING:
    from ..client import MediaServerClient

logger = logging.getLogger(__name__)


def chunked_upload(
    client: MediaServerClient,
    file_path: Path | str,
    remote_path: str | None = None,
    progress_callback: Callable[[float], None] | None = None,
    timeout: int | None = 300,
    max_retry: int | None = 10
) -> str:
    """
    Function to send a file using the chunked upload.
    """
    if remote_path and not re.match(r'^[A-Za-z0-9_-]{10,50}/.+$', remote_path):
        raise ValueError('Invalid "remote_path" argument value.')

    logger.info('Uploading file "%s".', file_path.name)

    max_retry = client.get_max_retry(max_retry)
    url_prefix = 'medias/resource/' if client.get_server_version() < (8, 2) else ''
    file_path = Path(file_path)

    # Get information on file
    chunk_size = client.conf['UPLOAD_CHUNK_SIZE']
    total_size = file_path.stat().st_size
    chunks_count = math.ceil(total_size / chunk_size)

    # Send chunks
    chunk_index = 0
    start_offset = 0
    end_offset = min(chunk_size, total_size) - 1
    data = {}
    url = client.get_full_url(url_prefix + 'upload/')
    begin = time.time()
    with open(file_path, 'rb') as fo:
        chunk = fo.read(chunk_size)
        while chunk:
            # Send chunk
            chunk_index += 1
            logger.debug(f'Uploading chunk {chunk_index}/{chunks_count}.')
            headers = {'Content-Range': f'bytes {start_offset}-{end_offset}/{total_size}'}
            files = {'file': (file_path.name, chunk)}
            tried = 0
            while True:
                tried += 1
                try:
                    # Use client.request to handle retry for offset errors
                    response = client.request(
                        url,
                        method='post',
                        headers=headers,
                        data=data,
                        files=files,
                        timeout=timeout
                    )
                    break
                except client.RequestError as err:
                    if err.status_code == 400:
                        try:
                            offset = int(err.response.get('offset'))
                        except (ValueError, TypeError):
                            offset = -1
                        if tried > 1 and offset == end_offset + 1 and 'upload_id' in data:
                            # The chunk sent was already received and due to an other error, the request was retried
                            logger.info(f'Offset issue detected during upload, ignoring error: {err}')
                            break
                        # No need to retry for other 400 errors, the result will be the same
                        logger.error(
                            f'Chunk upload failed, tried {tried} times '
                            f'(no retry for the status code {err.status_code} in chunk upload).'
                        )
                        raise err
                    elif err.status_code in client.conf['RETRY_EXCEPT']:
                        logger.error(
                            f'Chunk upload failed, tried {tried} times '
                            f'(no retry for the status code {err.status_code}).'
                        )
                        raise err
                    elif tried > max_retry:
                        logger.error(
                            f'Chunk upload failed, tried {tried} times '
                            f'(reached max retry count).'
                        )
                        raise err
                    else:
                        # Wait longer after every attempt
                        delay = 3 * tried * tried
                        logger.error(
                            f'Chunk upload failed, tried {tried} times '
                            f'(max {max_retry}), retrying in {delay}s.'
                        )
                        time.sleep(delay)

            # Notify progress callback
            if progress_callback:
                progress_callback(0.9 * end_offset / total_size)

            # Get data for next chunk
            if 'upload_id' not in data:
                data['upload_id'] = response['upload_id']
            start_offset += chunk_size
            end_offset = min(end_offset + chunk_size, total_size - 1)
            chunk = fo.read(chunk_size)

    bandwidth = total_size / (time.time() - begin)
    logger.info(f'Upload finished, average bandwidth was {bytes_repr(bandwidth)}/s.')

    # Mark file as completed
    data['no_md5'] = 'yes'  # The md5 check is deprecated since 2023-04-20 and has been removed in Nudgis v11.3.1
    data['expected_size'] = str(total_size)
    if remote_path:
        data['path'] = remote_path
    response = client.api(
        url_prefix + 'upload/complete/',
        method='post',
        data=data,
        timeout=timeout,
        max_retry=max_retry
    )

    # Notify progress callback
    if progress_callback:
        progress_callback(1.)
    return data['upload_id']


def hls_upload(
    client: MediaServerClient,
    m3u8_path: Path | str,
    remote_dir: str = '',
    progress_callback: Callable[[float], None] | None = None,
    timeout: int | None = 600,
    max_retry: int | None = 10
) -> str:
    """
    Method to upload an HLS video (m3u8 + ts fragments).
    This method is faster than "chunked_upload" because "chunked_upload" is very slow for a large number of tiny files.
    The directory containing ts files must have the same name as the m3u8 file.
    """
    if client.get_server_version() < (8, 2):
        raise RuntimeError('The MediaServer version does not support HLS upload.')

    m3u8_path = Path(m3u8_path)
    if not m3u8_path.is_file():
        raise ValueError(f'The given m3u8 file "{m3u8_path}" does not exist.')
    ts_dir = m3u8_path.parent / m3u8_path.name.strip('.').rsplit('.', 1)[0]
    if not ts_dir.is_dir():
        raise ValueError(f'The ts directory "{ts_dir}" of the m3u8 file "{m3u8_path}" does not exist.')
    if remote_dir and not re.match(r'^[A-Za-z0-9_-]{10,50}$', remote_dir):
        raise ValueError('Invalid "remote_dir" argument value.')

    logger.info('Uploading HLS "%s".', m3u8_path.name)

    # Get configuration
    max_size = client.conf['UPLOAD_CHUNK_SIZE']
    logger.debug(f'HLS upload requests size limit: {max_size} B.')
    max_files = client.conf['UPLOAD_MAX_FILES']
    logger.debug(f'HLS upload files per request limit: {max_files}.')

    # Send ts fragments
    files_list = []
    files_size = 0
    total_size = 0
    total_files_count = 1
    ts_fragments = sorted(ts_dir.iterdir(), key=lambda item: item.name)
    begin = time.time()
    for ts_path in ts_fragments:
        if not ts_path.is_file():
            logger.warning(
                f'Found an element which is not a file in the ts fragments dir "{ts_path.name}". '
                'The element will be ignored.'
            )
            continue

        size = ts_path.stat().st_size
        files_size += size
        files_list.append((ts_path, size))
        total_files_count += 1

        if files_size > max_size or len(files_list) >= max_files:
            # Send files in list
            logger.info(
                f'Uploading {len(files_list)} files ({(files_size / 1_000_000):.2f} MB, only fragments) '
                f'of "{ts_dir}" in one request.'
            )
            total_size += files_size
            data = dict(dir_name=remote_dir, hls_name=ts_dir.name)

            # Get files size and content (load in RAM to avoid triggering open file limit)
            files = {}
            for path, size in files_list:
                data[path.name] = str(size)
                with open(path, 'rb') as fo:
                    files[path.name] = (path.name, fo.read())
            response = client.api(
                'upload/hls/',
                method='post',
                data=data,
                files=files,
                timeout=timeout,
                max_retry=max_retry
            )

            # Notify progress callback
            if progress_callback:
                progress_callback(total_files_count / len(ts_fragments))
            files_list = []
            files_size = 0
            if not remote_dir:
                remote_dir = response['dir_name']

    # Send remaining ts fragments and m3u8 file
    size = m3u8_path.stat().st_size
    files_size += size
    files_list.append((m3u8_path, size))
    logger.info(
        f'Uploading {len(files_list)} files ({(files_size / 1_000_000):.2f} MB, fragments and the playlist) '
        f'of "{ts_dir}" in one request.'
    )
    total_size += files_size
    data = dict(dir_name=remote_dir, hls_name=ts_dir.name)
    files = {}

    # Get files size and content (load in RAM to avoid triggering open file limit)
    for path, size in files_list:
        data[path.name] = str(size)
        with open(path, 'rb') as fo:
            files[path.name] = (path.name, fo.read())
    client.api(
        'upload/hls/',
        method='post',
        data=data,
        files=files,
        timeout=timeout,
        max_retry=max_retry
    )
    bandwidth = total_size / (time.time() - begin)
    logger.info(
        f'Upload finished ({total_files_count} files in "{remote_dir}"), '
        f'average bandwidth: {bytes_repr(bandwidth)}/s'
    )

    # Notify progress callback
    if progress_callback:
        progress_callback(1.)
    return remote_dir
