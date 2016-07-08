#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2016, Florent Thiery

import os
import sys
import time
import math
import hashlib
import requests
import json

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


def save_config(config_dict, config_fpath):
    with open(config_fpath, 'w') as config_file:
        json.dump(config_dict, config_file, sort_keys=True, indent=4, separators=(',', ': '))


def read_config(config_fpath):
    print('Reading %s' % config_fpath)
    with open(config_fpath, 'r') as config_file:
        return json.load(config_file)


class MediaServerClient:
    def __init__(self, config):
        self.config = config
        if not config['VERIFY_SSL']:
            from requests.packages.urllib3.exceptions import InsecureRequestWarning
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        self.UPLOAD_CHUNK_SIZE = config['UPLOAD_CHUNK_SIZE']

    def request(self, url, method='get', data={}, params={}, files={}, headers={}, json=True, timeout=10):
        global session
        if session is None:
            session = requests.Session()

        if method == 'get':
            req_function = session.get
            params['api_key'] = self.config['API_KEY']
        else:
            req_function = session.post
            data['api_key'] = self.config['API_KEY']

        req_args = {
            'url': url,
            'headers': headers,
            'params': params,
            'data': data,
            'timeout': timeout,
            'proxies': self.config['PROXIES'],
            'verify': self.config['VERIFY_SSL'],
            'files': files,
        }
        resp = req_function(**req_args)
        if resp.status_code != 200:
            raise Exception('HTTP %s error on %s: %s' % (resp.status_code, url, resp.text))
        return resp.json() if json else resp.text.strip()

    def api(self, suffix, *args, **kwargs):
        BASE_URL = requests.compat.urljoin(self.config['SERVER_URL'], 'api/v2/')
        suffix.lstrip('/')
        kwargs['url'] = requests.compat.urljoin(BASE_URL, suffix)
        return self.request(*args, **kwargs)

    def read_in_chunks(self, file_object):
        while True:
            data = file_object.read(self.UPLOAD_CHUNK_SIZE)
            if not data:
                break
            yield data

    def chunked_upload(self, file_path, title="", category="Unsorted", **kwargs):
        total_size = os.path.getsize(file_path)
        chunks_count = math.ceil(total_size / self.UPLOAD_CHUNK_SIZE)
        start_offset = 0
        end_offset = min(self.UPLOAD_CHUNK_SIZE, total_size) - 1
        upload_data = {}
        md5sum = hashlib.md5()
        begin = time.time()
        with open(file_path, 'rb') as file_object:
            for index, chunk in enumerate(self.read_in_chunks(file_object)):
                print('Uploading chunk [%s/%s]' % (index + 1, chunks_count))
                md5sum.update(chunk)
                files = {'file': (os.path.basename(file_path), chunk)}
                headers = {'Content-Range': 'bytes %(start_offset)s-%(end_offset)s/%(total_size)s' % locals()}
                resp = self.api('medias/resource/upload/', method='post', data=upload_data, files=files, headers=headers)
                if 'upload_id' not in upload_data:
                    upload_data['upload_id'] = resp['upload_id']
                start_offset += self.UPLOAD_CHUNK_SIZE
                end_offset = min(end_offset + self.UPLOAD_CHUNK_SIZE, total_size - 1)
        upload_data['md5'] = md5sum.hexdigest()
        bandwidth = total_size*8/((time.time() - begin)*1000000)
        print('Upload finished, average bandwidth: %.2f Mbits/s' % bandwidth)
        resp = self.api('medias/resource/upload/complete/', method='post', data=upload_data, timeout=600)
        metadata = {
            'title': title,
            'code': upload_data['upload_id'],
            'origin': self.config['CLIENT_ID'],
        }
        arguments = {**metadata, **kwargs}
        resp = self.api('medias/add/', method='post', data=arguments)
        return resp


if __name__ == '__main__':
    try:
        config_fpath = sys.argv[1]
    except IndexError:
        config_fpath = 'config.json'
    try:
        config = read_config(config_fpath)
        for k in CONFIG_DEFAULT.keys():
            changed = False
            if config.get(k) is None:
                config[k] = CONFIG_DEFAULT[k]
                changed = True
        if changed:
            save_config(config, config_fpath)
            print('Config updated and saved to %s' % config_fpath)
    except Exception as e:
        print('Error while parsing configuration file, using defaults (%s)' % e)
        config = CONFIG_DEFAULT

    ms = MediaServerClient(config)

    # print(ms.api('users/add/', method='post', data={'email': 'test@test.com'}))
    # ms.chunked_upload('/tmp/test.mp4', title='Test multichunk upload', layout='webinar', detect_slide=['0_0-640_480-750'])
    # fname = sys.argv[1]
