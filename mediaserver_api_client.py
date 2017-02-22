#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2017, Florent Thiery, Stéphane Diemer

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

    def request(self, url, method='get', data=None, params=None, files=None, headers=None, parse_json=True, timeout=10):
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
        if parse_json:
            response = req.json()
            if 'success' in response and not response['success']:
                raise Exception('API call failed: %s' % (response.get('error', response.get('message', 'No information on error.'))))
        else:
            response = req.text.strip()
        return response

    def api(self, suffix, *args, **kwargs):
        kwargs['url'] = self.config['SERVER_URL'].strip('/') + '/api/v2/' + (suffix.rstrip('/') + '/').lstrip('/')
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

    def add_media(self, title=None, file_path=None, **kwargs):
        if not title and not file_path:
            raise ValueError('You should give a title or a file to create a media.')
        metadata = kwargs
        metadata['origin'] = self.config['CLIENT_ID']
        if title:
            metadata['title'] = title
        if file_path:
            metadata['code'] = self.chunked_upload(file_path)
        response = self.api('medias/add/', method='post', data=metadata, timeout=600)
        return response

    def remove_all_content(self):
        print('Remove all content')
        channels = self.api('/channels/tree')['channels']
        while msc.api('/channels/tree')['channels']:
            for c in channels:
                c_oid = c['oid']
                msc.api('/channels/delete', method='post', data={'oid': c_oid, 'delete_content': 'yes'})
                print('Emptied channel %s' % c_oid)
            channels = msc.api('/channels/tree')['channels']

    def import_users_csv(self, csv_path):
        groupname = "Users imported from csv on %s" % time.ctime()
        groupid = self.api('groups/add', method='post', data={'name': groupname}).get('id')
        print('Created group %s with id %s' % (groupname, groupid))
        with open(csv_path, 'r') as f:
            d = f.read()
            for index, l in enumerate(d.split('\n')):
                # Skip first line (contains header)
                if l and index > 0:
                    fields = [f.strip() for f in l.split(';')]
                    email = fields[2]
                    user = {
                        'email': email,
                        'first_name': fields[0],
                        'last_name': fields[1],
                        'company': fields[3],
                        'username': email,
                        'is_active': 'true',
                    }
                    print('Adding %s' % email)
                    try:
                        print(self.api('users/add/', method='post', data=user))
                    except Exception as e:
                        print('Error : %s' % e)
                    print('Adding user %s to group %s' % (email, groupname))
                    try:
                        print(self.api('groups/members/add/', method='post', data={'id': groupid, 'user_email': email}))
                    except Exception as e:
                        print('Error : %s' % e)


if __name__ == '__main__':
    log_format = '%(asctime)s %(name)s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    urllib3_logger = logging.getLogger('requests.packages.urllib3')
    urllib3_logger.setLevel(logging.WARNING)

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(config_path)
    # ping
    print(msc.api('/', method='get'))

    #d = msc.api('/lives/prepare', method='post')
    #if d['success']:
    #    oid = d['oid']
    #    rtmp_uri = d['publish_uri']
    #    print(oid, rtmp_uri)
    #    print(msc.api('/lives/start', method='post', data={'oid': oid}))
    #    print(msc.api('/lives/stop', method='post', data={'oid': oid}))

    #def remove_all_users():
    #    print('Remove all users')
    #    users = msc.api('/users')['users']
    #    for user in users:
    #        msc.api('/users/delete', method='get', params={'id': user['id']})

    # add media with a video
    #print(msc.add_media('Test multichunk upload mp4', file_path='test.mp4', layout='webinar', detect_slide=['0_0-640_480-750']))

    # add media with a zip
    # print(msc.add_media('Test multichunk upload zip', file_path='/tmp/test.zip'))

    # add user
    # print(msc.api('users/add/', method='post', data={'email': 'test@test.com'}))

    # add users with csv file; example file (header should be included):
    # Firstname;Lastname;Email;Company
    # Albert;Einstein;albert.einstein@test.com;Humanity
    # msc.import_users_csv('users.csv')
