#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
MediaServer client class

Copyright 2019, Florent Thiery, Stéphane Diemer
'''
import logging
import requests
import time
from .lib import configuration as configuration_lib
from .lib import content as content_lib
from .lib import upload as upload_lib
from .lib import users_csv as users_csv_lib

logger = logging.getLogger('ms_client.client')


class MediaServerClient():
    '''
    MediaServer API client class
    '''
    DEFAULT_CONF = None  # can be either a dict, a path (`str` object) or a unix user (`unix:msuser` for example)

    def __init__(self, local_conf=None, setup_logging=True):
        # "local_conf" can be either a dict, a path (`str` object) or a unix user (`unix:msuser` for example)
        # Setup logging
        if setup_logging:
            log_format = '%(asctime)s %(name)s %(levelname)s %(message)s'
            logging.basicConfig(level=logging.INFO, format=log_format)
        # Read conf file
        self.conf_checked = False
        self.conf = self.load_conf(local_conf)
        if not self.conf['VERIFY_SSL']:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Request session
        self.session = None

    def load_conf(self, local_conf):
        self.local_conf = local_conf
        conf = configuration_lib.load_conf(self.DEFAULT_CONF, self.local_conf)
        self.conf_checked = False
        return conf

    def update_conf(self, key, value):
        self.conf[key] = value
        # write change in local_conf if it is a path
        configuration_lib.update_conf(self.local_conf, key, value)

    def check_conf(self):
        if not self.conf_checked:
            configuration_lib.check_conf(self.conf)
            self.conf_checked = True

    def check_server(self):
        return self.api('/', timeout=5)

    def get_server_version(self):
        if not hasattr(self, '_server_version'):
            try:
                response = self.api('/', timeout=5)
                version_str = response.get('mediaserver') or '6.5.4'  # "mediaserver" key was added in version 6.6.0
                self._server_version = tuple([int(i) for i in version_str.split('.')])
            except Exception as e:
                raise Exception('Failed to get MediaServer version: %s', e)
            else:
                logger.info('MediaServer version is: %s', self._server_version)
        return self._server_version

    def request(self, url, method='get', data=None, params=None, files=None, headers=None, parse_json=True, timeout=0, ignore_404=False):
        if self.session is None and self.conf['USE_SESSION']:
            self.session = requests.Session()

        if method == 'get':
            req_function = self.session.get if self.session is not None else requests.get
            params = params or dict()
            params['api_key'] = self.conf['API_KEY']
        else:
            req_function = self.session.post if self.session is not None else requests.post
            data = data or dict()
            data['api_key'] = self.conf['API_KEY']

        req = req_function(
            url=url,
            headers=headers,
            params=params,
            data=data,
            files=files,
            timeout=timeout or self.conf['TIMEOUT'],
            proxies=self.conf['PROXIES'],
            verify=self.conf['VERIFY_SSL'],
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
        self.check_conf()

        begin = time.time()
        kwargs['url'] = self.conf['SERVER_URL'] + '/api/v2/' + (suffix.rstrip('/') + '/').lstrip('/')
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

    def hls_upload(self, *args, **kwargs):
        return upload_lib.hls_upload(self, *args, **kwargs)

    def chunked_upload(self, *args, **kwargs):
        return upload_lib.chunked_upload(self, *args, **kwargs)

    def add_media(self, *args, **kwargs):
        return content_lib.add_media(self, *args, **kwargs)

    def remove_all_content(self, *args, **kwargs):
        return content_lib.remove_all_content(self, *args, **kwargs)

    def import_users_csv(self, *args, **kwargs):
        return users_csv_lib.import_users_csv(self, *args, **kwargs)
