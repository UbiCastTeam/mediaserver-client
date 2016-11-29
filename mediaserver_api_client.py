#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2016, Florent Thiery

import hashlib
import json
import logging
import math
import os
import requests
import sys
import time

logger = logging.getLogger('mediaserver_client')

MiB = 1024 * 1024
session = None

# Do not edit this directly, create a config.json file instead
CONFIG_DEFAULT = {
    'SERVER_URL': 'https://my.mediaserver.net',
    'API_KEY': 'my-api-key',
    'PROXIES': {'http': '', 'https': ''},
    'UPLOAD_CHUNK_SIZE': 5 * MiB,
    'VERIFY_SSL': False,
    'CLIENT_ID': 'python-api-client',
}


class MediaServerClient:
    def __init__(self, config_path=None):
        self.config = CONFIG_DEFAULT.copy()
        self.config_path = config_path or 'config.json'
        if os.path.exists(self.config_path):
            self.load_config()
        if not self.config['VERIFY_SSL']:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def save_config(self):
        with open(self.config_path, 'w') as fo:
            json.dump(self.config, fo, sort_keys=True, indent=4, separators=(',', ': '))

    def load_config(self):
        logger.debug('Reading %s', self.config_path)
        try:
            with open(self.config_path, 'r') as fo:
                self.config.update(json.load(fo))
        except Exception as e:
            logger.error('Error while parsing configuration file, using defaults (%s).', e)

    def request(self, url, method='get', data=None, params=None, files=None, headers=None, json=True, timeout=10):
        global session
        if session is None:
            session = requests.Session()

        if method == 'get':
            req_function = session.get
            params = params or dict()
            params['api_key'] = self.config['API_KEY']
        else:
            req_function = session.post
            data = data or dict()
            data['api_key'] = self.config['API_KEY']

        req_args = {
            'url': url,
            'headers': headers,
            'params': params,
            'data': data,
            'files': files,
            'timeout': timeout,
            'proxies': self.config['PROXIES'],
            'verify': self.config['VERIFY_SSL'],
        }
        req = req_function(**req_args)
        if req.status_code != 200:
            raise Exception('HTTP %s error on %s: %s' % (req.status_code, url, req.text))
        return req.json() if json else req.text.strip()

    def api(self, suffix, *args, **kwargs):
        kwargs['url'] = self.config['SERVER_URL'].strip('/') + '/api/v2/' + suffix.lstrip('/')
        return self.request(*args, **kwargs)

    def chunked_upload(self, file_path):
        chunk_size = self.config['UPLOAD_CHUNK_SIZE']
        total_size = os.path.getsize(file_path)
        chunks_count = math.ceil(total_size / chunk_size)
        chunk_index = 0
        start_offset = 0
        end_offset = min(chunk_size, total_size) - 1
        data = dict()
        md5sum = hashlib.md5()
        begin = time.time()
        with open(file_path, 'rb') as file_object:
            while True:
                chunk = file_object.read(chunk_size)
                if not chunk:
                    break
                chunk_index += 1
                logger.debug('Uploading chunk [%s/%s]', chunk_index, chunks_count)
                md5sum.update(chunk)
                files = {'file': (os.path.basename(file_path), chunk)}
                headers = {'Content-Range': 'bytes %s-%s/%s' % (start_offset, end_offset, total_size)}
                response = self.api('medias/resource/upload/', method='post', data=data, files=files, headers=headers)
                if 'upload_id' not in data:
                    data['upload_id'] = response['upload_id']
                start_offset += chunk_size
                end_offset = min(end_offset + chunk_size, total_size - 1)
        bandwidth = total_size * 8 / ((time.time() - begin) * 1000000)
        logger.debug('Upload finished, average bandwidth: %.2f Mbits/s', bandwidth)
        data['md5'] = md5sum.hexdigest()
        response = self.api('medias/resource/upload/complete/', method='post', data=data, timeout=600)
        return data['upload_id']

    def add_media(self, title, file_path=None, **kwargs):
        metadata = kwargs
        metadata['title'] = title
        metadata['origin'] = self.config['CLIENT_ID']
        if file_path:
            metadata['code'] = self.chunked_upload(file_path)
        response = self.api('medias/add/', method='post', data=metadata)
        return response


if __name__ == '__main__':
    log_format = '%(asctime)s %(name)s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    urllib3_logger = logging.getLogger('requests.packages.urllib3')
    urllib3_logger.setLevel(logging.WARNING)

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(config_path)
    # ping
    print(msc.api('/', method='get'))

    # add media with a video
    # print(msc.add_media('Test multichunk upload mp4', file_path='/tmp/test.mp4', layout='webinar', detect_slide=['0_0-640_480-750']))

    # add media with a zip
    # print(msc.add_media('Test multichunk upload zip', file_path='/tmp/test.zip'))

    # add user
    # print(ms.api('users/add/', method='post', data={'email': 'test@test.com'}))
