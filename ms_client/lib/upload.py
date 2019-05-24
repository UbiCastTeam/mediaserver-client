#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
MediaServer client upload library
This module is not intended to be used directly, only the client class should be used.
'''
import hashlib
import logging
import math
import os
import time

logger = logging.getLogger('ms_client.lib.upload')


def chunked_upload(client, file_path, remote_path=None, progress_callback=None, progress_data=None, check_md5=True):
    url_prefix = 'medias/resource/' if client.get_server_version() < (8, 2) else ''
    chunk_size = client.conf['UPLOAD_CHUNK_SIZE']
    total_size = os.path.getsize(file_path)
    chunks_count = math.ceil(total_size / chunk_size)
    chunk_index = 0
    start_offset = 0
    end_offset = min(chunk_size, total_size) - 1
    data = dict()
    if check_md5:
        md5sum = hashlib.md5()
    begin = time.time()
    with open(file_path, 'rb') as file_object:
        while True:
            chunk = file_object.read(chunk_size)
            if not chunk:
                break
            chunk_index += 1
            logger.debug('Uploading chunk %s/%s.', chunk_index, chunks_count)
            if check_md5:
                md5sum.update(chunk)
            files = {'file': (os.path.basename(file_path), chunk)}
            headers = {'Content-Range': 'bytes %s-%s/%s' % (start_offset, end_offset, total_size)}
            response = client.api(url_prefix + 'upload/', method='post', data=data, files=files, headers=headers, timeout=3600, max_retry=5)
            if progress_callback:
                pdata = progress_data or dict()
                progress_callback(0.9 * end_offset / total_size, **pdata)
            if 'upload_id' not in data:
                data['upload_id'] = response['upload_id']
            start_offset += chunk_size
            end_offset = min(end_offset + chunk_size, total_size - 1)
    bandwidth = total_size * 8 / ((time.time() - begin) * 1000000)
    logger.debug('Upload finished, average bandwidth: %.2f Mbits/s', bandwidth)
    if check_md5:
        data['md5'] = md5sum.hexdigest()
    else:
        data['no_md5'] = 'yes'
    if remote_path:
        data['path'] = remote_path
    response = client.api(url_prefix + 'upload/complete/', method='post', data=data, timeout=3600, max_retry=5)
    if progress_callback:
        pdata = progress_data or dict()
        progress_callback(1., **pdata)
    return data['upload_id']


def hls_upload(client, m3u8_path, remote_dir='', progress_callback=None, progress_data=None):
    '''
    Method to upload an HLS video (m3u8 + ts fragments).
    This method is faster than "chunked_upload" because "chunked_upload" is very slow for a large number of tiny files.
    The directory containing ts files must have the same name as the m3u8 file.
    '''
    if client.get_server_version() < (8, 2):
        raise Exception('The MediaServer version does not support HLS upload.')
    if not os.path.isfile(m3u8_path):
        raise ValueError('The given m3u8 file "%s" does not exist.' % m3u8_path)
    ts_dir = '.'.join(m3u8_path.split('.')[:-1])
    if not os.path.isdir(ts_dir):
        raise ValueError('The ts directory "%s" of the m3u8 file "%s" does not exist.' % (ts_dir, m3u8_path))
    remote_dir = remote_dir.strip(' \t\n\r/\\')
    remote_name = os.path.basename(ts_dir)
    # Get configuration
    max_size = client.conf['UPLOAD_CHUNK_SIZE']
    logger.debug('HLS upload requests size limit: %s B.', max_size)
    # Limit number of open files if max size is above or almost equal to MediaServer memory upload limit
    max_files = 500 if max_size > 30000000 else None
    logger.debug('HLS upload files per request limit: %s.', max_files)
    # Send ts fragments
    files_list = list()
    files_size = 0
    total_size = 0
    total_files_count = 1
    ts_fragments = os.listdir(ts_dir)
    ts_fragments.sort()
    begin = time.time()
    for name in ts_fragments:
        ts_path = os.path.join(ts_dir, name)
        if not os.path.isfile(ts_path):
            logger.warning('Found a non file object in the ts fragments dir "%s". The object will be ignored.')
            continue
        size = os.path.getsize(ts_path)
        files_size += size
        files_list.append((ts_path, size))
        total_files_count += 1
        if files_size > max_size or (max_files and len(files_list) >= max_files):
            # Send files in list
            logger.info('Uploading %s files (%.2f MiB, only fragments) of "%s" in one request.', len(files_list), files_size / (1024 ** 2), ts_dir)
            total_size += files_size
            data = dict(dir_name=remote_dir, hls_name=remote_name)
            files = dict()
            # Get files size and content (load in RAM to avoid triggering open file limit)
            for path, size in files_list:
                name = os.path.basename(path)
                data[name] = str(size)
                with open(path, 'rb') as fo:
                    files[name] = (name, fo.read())
            response = client.api('upload/hls/', method='post', data=data, files=files, timeout=3600, max_retry=5)
            if progress_callback:
                pdata = progress_data or dict()
                progress_callback(total_files_count / len(ts_fragments), **pdata)
            files_list = list()
            files_size = 0
            if not remote_dir:
                remote_dir = response['dir_name']
    # Send remaining ts fragments and m3u8 file
    size = os.path.getsize(m3u8_path)
    files_size += size
    files_list.append((m3u8_path, size))
    logger.info('Uploading %s files (%.2f MiB, fragments the playlist) of "%s" in one request.', len(files_list), files_size / (1024 ** 2), ts_dir)
    total_size += files_size
    data = dict(dir_name=remote_dir, hls_name=remote_name)
    files = dict()
    # Get files size and content (load in RAM to avoid triggering open file limit)
    for path, size in files_list:
        name = os.path.basename(path)
        data[name] = str(size)
        with open(path, 'rb') as fo:
            files[name] = (name, fo.read())
    client.api('upload/hls/', method='post', data=data, files=files, timeout=3600, max_retry=5)
    bandwidth = total_size * 8 / ((time.time() - begin) * 1000000)
    logger.info('Upload finished (%s files in "%s"), average bandwidth: %.2f Mbits/s', total_files_count, remote_dir, bandwidth)
    if progress_callback:
        pdata = progress_data or dict()
        progress_callback(1., **pdata)
    return remote_dir
