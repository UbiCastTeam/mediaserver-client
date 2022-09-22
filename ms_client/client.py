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


class MediaServerRequestError(Exception):
    def __init__(self, *args, **kwargs):
        self.status_code = kwargs.pop('status_code', None)
        self.error_code = kwargs.pop('error_code', None)
        super().__init__(*args, **kwargs)


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
        self.load_conf(local_conf)
        # Configure logging
        if setup_logging:
            level = getattr(logging, self.conf['LOG_LEVEL']) if self.conf.get('LOG_LEVEL') else logging.INFO
            root_logger = logging.getLogger('root')
            root_logger.setLevel(level)
            logger.setLevel(level)
            logging.captureWarnings(False)
            logger.debug('Logging conf set.')
        if not self.conf['VERIFY_SSL']:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Request session
        self.session = None

    def load_conf(self, local_conf):
        self.local_conf = local_conf
        self.conf = configuration_lib.load_conf(self.DEFAULT_CONF, self.local_conf)
        self.conf_checked = False
        return self.conf

    def update_conf(self, key, value):
        self.conf[key] = value
        # write change in local_conf if it is a path
        configuration_lib.update_conf(self.local_conf, key, value)

    def check_conf(self):
        if not self.conf_checked:
            configuration_lib.check_conf(self.conf)
            self.conf_checked = True

    def check_server(self):
        return self.api('/')

    def get_server_version(self):
        if not hasattr(self, '_server_version'):
            try:
                url = self.get_full_url('/')

                # api-key header was added in version 11.0.0, so we must authenticate using the previously
                # available api_key query string first to determine the version
                response = self.request(url, api_key_in_header=False)

                # "mediaserver" key was added in version 6.6.0
                version_str = response.get('mediaserver') or '6.5.4'
                self._server_version = tuple([int(i) for i in version_str.split('.')])
            except Exception as e:
                raise MediaServerRequestError(
                    'Failed to get MediaServer version: %s' % e,
                    status_code=getattr(e, 'status_code', None),
                    error_code=getattr(e, 'error_code', None)
                )
            else:
                logger.debug('MediaServer version is: %s', self._server_version)
        return self._server_version

    def request(self, url, method='get', data=None, params=None, files=None, headers=None, parse_json=True, timeout=None, stream=False, ignored_status_codes=None, ignored_error_strings=None, api_key_in_header=None):
        if ignored_status_codes is None:
            ignored_status_codes = list()

        if ignored_error_strings is None:
            ignored_error_strings = list()

        if self.session is None and self.conf['USE_SESSION']:
            self.session = requests.Session()

        if headers is None:
            headers = dict()
        if self.conf.get('LANGUAGE'):
            headers.setdefault('Accept-Language', self.conf['LANGUAGE'])

        if method in ['get', 'head']:
            params = params or dict()
            if method == 'get':
                req_function = self.session.get if self.session is not None else requests.get
            elif method == 'head':
                req_function = self.session.head if self.session is not None else requests.head
        else:
            req_function = self.session.post if self.session is not None else requests.post
            data = data or dict()

        api_key = self.conf.get('API_KEY')
        if api_key:
            # the api-key header was introduced in version 11.0.0
            # prefer this over the api_key query string by default to avoid leaking
            # the key in access logs and to preserve authentication when following
            # 302 redirections
            if api_key_in_header is False or self.get_server_version()[0] < 11:
                if method in ['get', 'head']:
                    params['api_key'] = api_key
                else:
                    data['api_key'] = api_key
            else:
                headers['api-key'] = api_key

        req = req_function(
            url=url,
            headers=headers,
            params=params,
            data=data,
            files=files,
            stream=stream,
            timeout=timeout or self.conf['TIMEOUT'],
            proxies=self.conf['PROXIES'],
            verify=self.conf['VERIFY_SSL'],
        )
        status_code = req.status_code
        if status_code != 200:
            error_message = req.text[:300]
            error_code = None
            if parse_json:
                try:
                    response = req.json()
                    error_message = response.get('error') or response.get('errors') or response.get('message') or error_message
                    error_code = response.get('code')
                except Exception:
                    pass

            # ignored status codes do not trigger retries nor raise exceptions
            if ignored_status_codes and status_code in ignored_status_codes:
                logger.info('Not raising exception for ignored status code %s on url %s ignored: %s' % (status_code, url, response))
                return None
            else:
                raise MediaServerRequestError(
                    'HTTP %s error on %s: %s' % (status_code, url, error_message),
                    status_code=status_code,
                    error_code=error_code
                )
        if stream or method == 'head':
            response = req
        elif parse_json:
            # code is 200
            response = req.json()
            if 'success' in response and not response['success']:
                error_message = response.get('error') or response.get('errors') or response.get('message') or 'No information on error.'
                error_code = response.get('code')
                for string in ignored_error_strings:
                    if string in str(error_message):
                        logger.info('Ignoring error on url %s : %s' % (url, error_message))
                        return None
                raise MediaServerRequestError(
                    'API call failed: %s' % error_message,
                    status_code=status_code,
                    error_code=error_code
                )
        else:
            response = req.text.strip()
        return response

    def get_full_url(self, suffix):
        return self.conf['SERVER_URL'] + '/api/v2/' + (suffix.rstrip('/') + '/').lstrip('/')

    def api(self, suffix, *args, **kwargs):
        self.check_conf()

        begin = time.time()
        kwargs['url'] = self.get_full_url(suffix)
        max_retry = kwargs.pop('max_retry', self.conf['MAX_RETRY'])
        if max_retry:
            retry_count = 1
            while True:
                try:
                    result = self.request(*args, **kwargs)
                    break
                except Exception as e:
                    # retry after errors like HTTP 400 errors "Offsets do not match", timeout or RemoteDisconnected errors
                    if retry_count >= max_retry or getattr(e, 'status_code', None) not in self.conf['RETRY_EXCEPT']:
                        raise
                    else:
                        # wait longer after every attempt
                        retry_time_s = 3 * retry_count * retry_count
                        logger.error('Request on %s failed (tried %s times, max %s), retrying in %ss, error was: %s' % (suffix, retry_count, max_retry, retry_time_s, e))
                        retry_count += 1
                        time.sleep(retry_time_s)
                        # seek to 0 in file objects
                        # (file objects using a value different from 0 as initial position is not supported)
                        if kwargs.get('files'):
                            # python-requests supports the following files arguments:
                            # files = {'file': open('report.xls', 'rb')}
                            # files = {'file': tuple}
                            # 2-tuples (filename, fileobj)
                            # 3-tuples (filename, fileobj, contentype)
                            # 4-tuples (filename, fileobj, contentype, custom_headers)

                            files = kwargs['files']

                            def is_fd(obj):
                                return hasattr(obj, 'seek')

                            for key, val in files.items():
                                fd = None

                                if is_fd(val):
                                    fd = val
                                else:
                                    for item in val:
                                        if is_fd(item):
                                            fd = item

                                if fd:
                                    logger.debug('Seeking file descriptor to 0')
                                    fd.seek(0)
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

    def download_metadata_zip(self, *args, **kwargs):
        return content_lib.download_metadata_zip(self, *args, **kwargs)

    def remove_all_content(self, *args, **kwargs):
        return content_lib.remove_all_content(self, *args, **kwargs)

    def import_users_csv(self, *args, **kwargs):
        return users_csv_lib.import_users_csv(self, *args, **kwargs)
