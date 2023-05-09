"""
MediaServer client class

Copyright 2019, Florent Thiery, Stéphane Diemer
"""
from json import JSONDecodeError
import logging
import requests
import time
from .lib import configuration as configuration_lib
from .lib import content as content_lib
from .lib import upload as upload_lib
from .lib import users_csv as users_csv_lib

logger = logging.getLogger(__name__)


class MediaServerRequestError(Exception):
    def __init__(self, message, status_code=None, error_code=None, response=None):
        self.status_code = status_code
        self.error_code = error_code
        self.response = response
        logger.error(message)
        super().__init__(message)


class MediaServerClient():
    """
    MediaServer API client class
    """
    # `DEFAULT_CONF` can be either a dict, a path (`str` object) or a unix user (`unix:msuser` for example).
    DEFAULT_CONF = None
    # `RequestError` is a reference to the error class to avoid circular imports in the client lib dir.
    RequestError = MediaServerRequestError

    def __init__(self, local_conf=None, setup_logging=True):
        # `local_conf` can be either a dict, a path (`str` object) or a unix user (`unix:msuser` for example)
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
        # Write change in local_conf if it is a path
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

                response = self.request(url, authenticate=False)

                # The "mediaserver" key was added in version 6.6.0
                version_str = response.get('mediaserver') or '6.5.4'
                self._server_version = tuple([int(i) for i in version_str.split('.')])
            except Exception as err:
                raise MediaServerRequestError(
                    f'Failed to get MediaServer version: {err}',
                    status_code=getattr(err, 'status_code', None),
                    error_code=getattr(err, 'error_code', None)
                ) from err
            else:
                logger.debug(f'MediaServer version is: {self._server_version}')
        return self._server_version

    def request(self, url, method='get', headers=None, params=None, data=None, files=None, parse_json=True,
                timeout=None, stream=False, ignored_status_codes=None, authenticate=True):
        self.check_conf()

        if ignored_status_codes is None:
            ignored_status_codes = []

        if self.conf['USE_SESSION']:
            if self.session is None:
                self.session = requests.Session()
            req_function = getattr(self.session, method)
        else:
            req_function = getattr(requests, method)

        if headers is None:
            headers = {}
        if self.conf.get('LANGUAGE'):
            headers.setdefault('Accept-Language', self.conf['LANGUAGE'])

        api_key = self.conf.get('API_KEY')
        if api_key and authenticate:
            # The api-key header was introduced in version 11.0.0.
            # Prefer this over the api_key query string by default to avoid leaking
            # the key in access logs and to preserve authentication when following
            # 302 redirections
            if self.get_server_version()[0] < 11:
                if method in ['get', 'head']:
                    if params is None:
                        params = {}
                    params['api_key'] = api_key
                else:
                    if data is None:
                        data = {}
                    data['api_key'] = api_key
            else:
                headers['api-key'] = api_key

        try:
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
                allow_redirects=True,
            )
            status_code = req.status_code
        except Exception as err:
            raise MediaServerRequestError(
                f'Connection error on "{url}": {err}',
                status_code=0,
            ) from err

        # Success and cases for which no decoding is required
        if status_code == 200:
            if stream or method == 'head':
                return req
            if not parse_json:
                return req.text

        # Get response
        if parse_json:
            try:
                response = req.json()
            except JSONDecodeError as err:
                response = {'raw': req.text}
                if status_code == 200:
                    raise MediaServerRequestError(
                        f'API call failed on "{url}": Failed to decode JSON: {err}',
                        status_code=status_code,
                        response=response,
                    ) from err
        else:
            response = req.text

        # Failure if code is not 200 or success is False
        # The success check is for versions < 11.0.0
        if status_code != 200 or not response.get('success', True):
            error_message = None
            error_code = None
            if parse_json:
                error_message = response.get('error') or response.get('errors') or response.get('message')
                error_code = response.get('code')
            if not error_message:
                error_message = req.text[:200]

            if status_code == 200:
                raise MediaServerRequestError(
                    f'API call failed on "{url}": {error_message}',
                    status_code=status_code,
                    error_code=error_code,
                    response=response,
                )
            elif ignored_status_codes and status_code in ignored_status_codes:
                # Ignored status codes do not trigger retries nor raise exceptions
                logger.info(
                    f'Not raising exception for ignored status code {status_code} on url {url} ignored: {response}'
                )
                return None
            else:
                raise MediaServerRequestError(
                    f'HTTP {status_code} error on "{url}": {error_message}',
                    status_code=status_code,
                    error_code=error_code,
                    response=response,
                )

        return response

    def get_full_url(self, suffix):
        return self.conf['SERVER_URL'] + '/api/v2/' + (suffix.rstrip('/') + '/').lstrip('/')

    def get_max_retry(self, max_retry=None):
        value = max_retry if max_retry is not None else (self.conf.get('MAX_RETRY') or 0)
        if value < 0:
            raise ValueError('The "max_retry" argument must be greater than or equal 0.')
        return value

    def api(self, suffix, *args, **kwargs):
        begin = time.time()
        kwargs['url'] = self.get_full_url(suffix)
        max_retry = self.get_max_retry(kwargs.pop('max_retry', None))
        if not max_retry:
            result = self.request(*args, **kwargs)
        else:
            tried = 0
            while True:
                tried += 1
                try:
                    result = self.request(*args, **kwargs)
                    break
                except MediaServerRequestError as err:
                    # Retry after errors like timeout or RemoteDisconnected errors
                    if err.status_code in self.conf['RETRY_EXCEPT']:
                        logger.error(
                            f'Request on "{suffix}" failed, tried {tried} times '
                            f'(no retry for the status code {err.status_code}).'
                        )
                        raise err
                    elif tried > max_retry:
                        logger.error(
                            f'Request on "{suffix}" failed, tried {tried} times '
                            f'(reached max retry count).'
                        )
                        raise err
                    else:
                        # Wait longer after every attempt
                        delay = 3 * tried * tried
                        logger.error(
                            f'Request on "{suffix}" failed, tried {tried} times '
                            f'(max {max_retry}), retrying in {delay}s.'
                        )
                        time.sleep(delay)
                        # Seek to 0 in file objects
                        # (file objects using a value different from 0 as initial position is not supported)
                        if kwargs.get('files'):
                            # Python-requests supports the following files arguments:
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
        logger.debug(f'API call duration: {time.time() - begin:.2f} s - {suffix}.')
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
