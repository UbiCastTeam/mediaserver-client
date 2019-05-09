#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2017, Florent Thiery, Stéphane Diemer
# Source file:
# https://github.com/UbiCastTeam/mediaserver-client/blob/master/mediaserver_api_client.py

import hashlib
import json
import logging
import math
import os
import requests
import sys
import time

logger = logging.getLogger('mediaserver_client')

# Do not edit this directly, create a config.json file instead
CONFIG_DEFAULT = {
    'SERVER_URL': 'https://mediaserver.example.com',
    'API_KEY': 'the-api-key',
    'PROXIES': {'http': '', 'https': ''},
    'UPLOAD_CHUNK_SIZE': 5 * 1024 * 1024,  # 5 MiB
    'VERIFY_SSL': False,
    'CLIENT_ID': 'python-api-client',
    'USE_SESSION': True,
}


class MediaServerClient:
    '''
        Mediaserver api client

        There is some examples:

        Start/Stop a live
        #################

        .. code-block:: python

            d = msc.api('/lives/prepare', method='post')
            if d['success']:
                oid = d['oid']
                rtmp_uri = d['publish_uri']

                print(oid, rtmp_uri)

                print(msc.api('/lives/start', method='post', data={'oid': oid}))

                print(msc.api('/lives/stop', method='post', data={'oid': oid}))

        Remove all users function
        #########################

        .. code-block:: python

            def remove_all_users():
                print('Remove all users')
                users = msc.api('/users')['users']

                for user in users:
                    msc.api('/users/delete', method='get', params={'id': user['id']})

        Add media with a video, make it published at once
        #################################################

        .. code-block:: python

            print(msc.add_media('Test multichunk upload mp4', file_path='test.mp4', validated='yes', speaker_email='user@domain.com'))

        Create user personal channel and upload into it
        ###############################################

        .. code-block:: python

            personal_channel_oid = msc.api('/channels/personal/', method='get', params={'email': 'test@test.com'}).get('oid')

            respone_like = {
                'slug': 'testtestcom_05881',
                'oid': 'c125855df7d36iudslp3',
                'dbid': 113,
                'title': 'test@test.com',
                'success': True
            }
            if personal_channel_oid:
                print('Uploading to personal channel %s' % personal_channel_oid)

                print(msc.add_media('Test multichunk upload mp4', file_path='test.mp4', validated='yes', speaker_email='user@domain.com', channel=personal_channel_oid))

        Add media with a zip
        ####################

        .. code-block:: python

            print(msc.add_media('Test multichunk upload zip', file_path='/tmp/test.zip'))
            print(msc.add_media(file_path='test.mp4'))

        Add user
        ########

        .. code-block:: python

            print(msc.api('users/add/', method='post', data={'email': 'test@test.com'}))

        Add users with csv file; example file (header should be included):
        ##################################################################

        users.csv :

        .. code-block:: csv

            Firstname;Lastname;Email;Company
            Albert;Einstein;albert.einstein@test.com;Humanity

        .. code-block:: python

            msc.import_users_csv('users.csv')

        # Usage examples of annotation api
        ##################################

        POST

        .. code-block:: python

            print(msc.api('annotations/post', params={'oid': 'v125849d470d7v92kvtc', 'time': 1000,}))

        Get Chapters

        .. code-block:: python

            print(msc.api('annotations/chapters/list', params={'oid': 'v125849d470d7v92kvtc'}))

        Get types list and print chapters id

        .. code-block:: python

            response = msc.api('annotations/types/list', params={'oid': 'v125849d470d7v92kvtc'})
            for a in response['types']:
                if a['slug'] == 'chapter':
                    print(a['id'])

    '''
    def __init__(self, config_path=None, config_dict=None):
        self.session = None
        self.config = CONFIG_DEFAULT.copy()
        self.config_checked = False
        self.load_config(config_path)
        if config_dict:
            self.update_config(config_dict)
        if not self.config['VERIFY_SSL']:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def save_config(self):
        with open(self.config_path, 'w') as fo:
            json.dump(self.config, fo, sort_keys=True, indent=4, separators=(',', ': '))

    def load_config(self, path=None):
        self.config_path = path or 'config.json'
        if os.path.exists(self.config_path):
            logger.debug('Reading configuration file "%s".', self.config_path)
            try:
                with open(self.config_path, 'r') as fo:
                    self.config.update(json.load(fo))
            except Exception as e:
                logger.error('Error while parsing configuration file, using defaults (%s).', e)
        else:
            error = 'Configuration file "%s" does not exist.' % self.config_path
            if path:
                logger.error(error)
                raise Exception(error)
            logger.debug(error)

    def update_config(self, data):
        if not isinstance(data, dict):
            raise TypeError('A dict is required to update the configuration (received a %s object).' % type(data))
        self.config.update(data)
        self.config_checked = False

    def check_config(self):
        # check that the MediaServer url is set
        if self.config_checked:
            return
        if self.config['SERVER_URL'] == CONFIG_DEFAULT['SERVER_URL']:
            raise ValueError('The value of SERVER_URL is using the default value. Please configure it.')
        self.config['SERVER_URL'] = self.config['SERVER_URL'].strip('/')
        if self.config['API_KEY'] == CONFIG_DEFAULT['API_KEY']:
            raise ValueError('The value of API_KEY is using the default value. Please configure it.')
        self.config_checked = True

    def check_server(self):
        self.api('/', timeout=5)

    def request(self, url, method='get', data=None, params=None, files=None, headers=None, parse_json=True, timeout=10, ignore_404=False):
        if self.session is None and self.config.get('USE_SESSION', True):
            self.session = requests.Session()

        if method == 'get':
            req_function = self.session.get if self.session is not None else requests.get
            params = params or dict()
            params['api_key'] = self.config['API_KEY']
        else:
            req_function = self.session.post if self.session is not None else requests.post
            data = data or dict()
            data['api_key'] = self.config['API_KEY']

        req = req_function(
            url=url,
            headers=headers,
            params=params,
            data=data,
            files=files,
            timeout=timeout,
            proxies=self.config['PROXIES'],
            verify=self.config['VERIFY_SSL'],
        )
        if req.status_code == 404 and ignore_404:
            logger.info('404 ignored on url %s.' % url)
            return None
        if req.status_code != 200:
            raise Exception('HTTP %s error on %s: %s' % (req.status_code, url, req.text))
        if parse_json:
            response = req.json()
            if 'success' in response and not response['success']:
                error_message = response.get('error') or response.get('errors') or response.get('message') or 'No information on error.'
                raise Exception('API call failed: %s' % error_message)
        else:
            response = req.text.strip()
        return response

    def api(self, suffix, *args, **kwargs):
        self.check_config()

        begin = time.time()
        kwargs['url'] = self.config['SERVER_URL'] + '/api/v2/' + (suffix.rstrip('/') + '/').lstrip('/')
        max_retry = kwargs.pop('max_retry', None)
        if max_retry:
            retry_count = 0
            while True:
                try:
                    result = self.request(*args, **kwargs)
                    break
                except Exception as e:
                    # do not retry when getting a 40X error
                    if retry_count >= max_retry or 'HTTP 40' in str(e):
                        raise
                    else:
                        retry_count += 1
                        logger.error('Request on %s failed (tried %s times): %s', suffix, retry_count, e)
                        time.sleep(3 * retry_count * retry_count)
                        # seek to 0 in file objects
                        # (file objects using a value different from 0 as initial position is not supported)
                        if kwargs.get('files'):
                            for file_o in kwargs['files']:
                                if hasattr(file_o, 'seek'):
                                    file_o.seek(0)
        else:
            result = self.request(*args, **kwargs)
        logger.debug('API call duration: %.2f s - %s', time.time() - begin, suffix)
        return result

    def hls_upload(self, m3u8_path, remote_dir='', progress_callback=None, progress_data=None):
        '''
        Method to upload an HLS video (m3u8 + ts fragments).
        This method is faster than "chunked_upload" because "chunked_upload" is very slow for a large number of tiny files.
        The directory containing ts files must have the same name as the m3u8 file.
        '''
        if not os.path.isfile(m3u8_path):
            raise ValueError('The given m3u8 file "%s" does not exist.' % m3u8_path)
        ts_dir = '.'.join(m3u8_path.split('.')[:-1])
        if not os.path.isdir(ts_dir):
            raise ValueError('The ts directory "%s" of the m3u8 file "%s" does not exist.' % (ts_dir, m3u8_path))
        remote_dir = remote_dir.strip(' \t\n\r/\\')
        remote_name = os.path.basename(ts_dir)
        # Send ts fragments
        max_size = self.config['UPLOAD_CHUNK_SIZE']
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
            if files_size > max_size:
                # Send files in list
                logger.info('Uploading %s files (%.2f MiB, only fragments) of "%s" in one request.', len(files_list), files_size / (1024 ** 2), ts_dir)
                total_size += files_size
                data = dict(dir_name=remote_dir, hls_name=remote_name)
                files = dict()
                for path, size in files_list:
                    data[os.path.basename(path)] = str(size)
                    files[os.path.basename(path)] = open(path, 'rb')
                response = self.api('upload/hls/', method='post', data=data, files=files, timeout=3600, max_retry=5)
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
        for path, size in files_list:
            data[os.path.basename(path)] = str(size)
            files[os.path.basename(path)] = open(path, 'rb')
        self.api('upload/hls/', method='post', data=data, files=files, timeout=3600, max_retry=5)
        bandwidth = total_size * 8 / ((time.time() - begin) * 1000000)
        logger.info('Upload finished (%s files in "%s"), average bandwidth: %.2f Mbits/s', total_files_count, remote_dir, bandwidth)
        if progress_callback:
            pdata = progress_data or dict()
            progress_callback(1., **pdata)
        return remote_dir

    def chunked_upload(self, file_path, remote_path=None, progress_callback=None, progress_data=None, check_md5=True):
        chunk_size = self.config['UPLOAD_CHUNK_SIZE']
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
                response = self.api('upload/', method='post', data=data, files=files, headers=headers, timeout=3600, max_retry=5)
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
        response = self.api('upload/complete/', method='post', data=data, timeout=3600, max_retry=5)
        if progress_callback:
            pdata = progress_data or dict()
            progress_callback(1., **pdata)
        return data['upload_id']

    def add_media(self, title=None, file_path=None, progress_callback=None, progress_data=None, **kwargs):
        if not title and not file_path:
            raise ValueError('You should give a title or a file to create a media.')
        self.check_server()
        metadata = kwargs
        metadata['origin'] = self.config['CLIENT_ID']
        if title:
            metadata['title'] = title
        if file_path:
            metadata['code'] = self.chunked_upload(file_path, progress_callback=progress_callback, progress_data=progress_data)
        response = self.api('medias/add/', method='post', data=metadata, timeout=3600)
        return response

    def remove_all_content(self):
        logger.info('Remove all content')
        channels = self.api('channels/tree/')['channels']
        while msc.api('channels/tree')['channels']:
            for c in channels:
                c_oid = c['oid']
                msc.api('channels/delete/', method='post', data={'oid': c_oid, 'delete_content': 'yes'})
                logger.info('Emptied channel %s' % c_oid)
            channels = msc.api('channels/tree/')['channels']

    def import_users_csv(self, csv_path):
        groupname = 'Users imported from csv on %s' % time.ctime()
        groupid = self.api('groups/add/', method='post', data={'name': groupname}).get('id')
        logger.info('Created group %s with id %s' % (groupname, groupid))
        with open(csv_path, 'r') as f:
            d = f.read()
            for index, l in enumerate(d.split('\n')):
                # Skip first line (contains header)
                if l and index > 0:
                    fields = [field.strip() for field in l.split(';')]
                    email = fields[2]
                    user = {
                        'email': email,
                        'first_name': fields[0],
                        'last_name': fields[1],
                        'company': fields[3],
                        'username': email,
                        'is_active': 'true',
                    }
                    logger.info('Adding %s' % email)
                    try:
                        logger.info(self.api('users/add/', method='post', data=user))
                    except Exception as e:
                        logger.error('Error : %s' % e)
                    logger.info('Adding user %s to group %s' % (email, groupname))
                    try:
                        logger.info(self.api('groups/members/add/', method='post', data={'id': groupid, 'user_email': email}))
                    except Exception as e:
                        logger.error('Error : %s' % e)


if __name__ == '__main__':
    log_format = '%(asctime)s %(name)s %(levelname)s %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.WARNING)

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(config_path)
    # ping
    print(msc.api('/'))
