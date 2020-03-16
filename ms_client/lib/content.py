#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
MediaServer client upload library
This module is not intended to be used directly, only the client class should be used.
'''
import logging
import os

logger = logging.getLogger('ms_client.lib.content')


def add_media(client, title=None, file_path=None, progress_callback=None, progress_data=None, timeout=3600, max_retry=None, **kwargs):
    if not title and not file_path:
        raise ValueError('You should give a title or a file to create a media.')
    client.get_server_version()  # ping server to test the connection and log version for debug
    metadata = kwargs
    metadata['origin'] = client.conf['CLIENT_ID']
    if title:
        metadata['title'] = title
    if file_path:
        metadata['code'] = client.chunked_upload(file_path, progress_callback=progress_callback, progress_data=progress_data)
    response = client.api('medias/add/', method='post', data=metadata, timeout=timeout, max_retry=max_retry)
    return response


def download_metadata_zip(client, media_oid, path, include_annotations=None, include_resources_links=None, force=False, timeout=3600, max_retry=None):
    if not media_oid:
        raise ValueError('You should give an object id to get the zip file.')
    valid_annotations = ('all', 'editorial', 'none')
    if include_annotations and include_annotations not in valid_annotations:
        raise ValueError('Invalid value given for "include_annotations". Valid values: %s.' % ', '.join(valid_annotations))
    valid_resources = ('yes', 'no')
    if include_resources_links and include_resources_links not in valid_resources:
        raise ValueError('Invalid value given for "include_resources_links". Valid values: %s.' % ', '.join(valid_resources))
    params = dict(oid=media_oid, annotations=include_annotations or 'none', resources=include_resources_links or 'no')
    if not force and os.path.isfile(path):
        size = str(os.path.getsize(path))
        req = client.api('medias/get/zip/', method='head', params=params, timeout=timeout, max_retry=max_retry)
        if req.headers.get('Content-Length') == size:
            logger.info('Skipping download of zip file for %s because the file already exists and has the correct size.', media_oid)
            return path
    req = client.api('medias/get/zip/', method='get', params=params, timeout=timeout, max_retry=max_retry, stream=True)
    with open(path, 'wb') as fo:
        for chunk in req.iter_content(10000000):  # 10 MB chunks
            fo.write(chunk)
    return path


def remove_all_content(client, timeout=None, max_retry=None):
    logger.info('Remove all content')
    channels = client.api('channels/tree/')['channels']
    while client.api('channels/tree')['channels']:
        for c in channels:
            c_oid = c['oid']
            client.api('channels/delete/', method='post', data={'oid': c_oid, 'delete_content': 'yes'}, timeout=timeout, max_retry=max_retry)
            logger.info('Emptied channel %s' % c_oid)
        channels = client.api('channels/tree/')['channels']
