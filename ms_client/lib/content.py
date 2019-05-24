#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
MediaServer client upload library
This module is not intended to be used directly, only the client class should be used.
'''
import logging

logger = logging.getLogger('ms_client.lib.content')


def add_media(client, title=None, file_path=None, progress_callback=None, progress_data=None, **kwargs):
    if not title and not file_path:
        raise ValueError('You should give a title or a file to create a media.')
    client.check_server()
    metadata = kwargs
    metadata['origin'] = client.conf['CLIENT_ID']
    if title:
        metadata['title'] = title
    if file_path:
        metadata['code'] = client.chunked_upload(file_path, progress_callback=progress_callback, progress_data=progress_data)
    response = client.api('medias/add/', method='post', data=metadata, timeout=3600)
    return response


def remove_all_content(client):
    logger.info('Remove all content')
    channels = client.api('channels/tree/')['channels']
    while client.api('channels/tree')['channels']:
        for c in channels:
            c_oid = c['oid']
            client.api('channels/delete/', method='post', data={'oid': c_oid, 'delete_content': 'yes'})
            logger.info('Emptied channel %s' % c_oid)
        channels = client.api('channels/tree/')['channels']
