# MediaServer client base configuration
# This file should not be modified directly, put your modification in another json file and give the path to the client.

BASE_CONF = {
    # Logging level
    'LOG_LEVEL': 'INFO',

    # URL of the MediaServer site
    'SERVER_URL': 'https://mediaserver',

    # API key of the MediaServer user account
    'API_KEY': '',

    # Client name used as origin name of added media
    # The "<host>" pattern is replaced by the system hostname
    'CLIENT_ID': 'python-api-client_<host>',

    # Language for API messages
    # Use None to use MediaServer default language
    # Supported languages are:
    # 'en', 'fr', 'de', 'es', 'nl', 'fi'
    'LANGUAGE': 'en',

    # Use a persistent session for requests
    # This is recommended especially for high availability deployments
    'USE_SESSION': True,

    # If failures should be auto-retried N times
    # Requires the use of a session.
    # Disabled by default
    'MAX_RETRY': 0,

    # List of response status codes for requests allowed to be retried
    # To get details on status codes:
    # https://fr.wikipedia.org/wiki/Liste_des_codes_HTTP
    # Connection errors are always included in requests to retry
    'RETRY_STATUS_CODES': {429, 500, 502, 503, 504, 507, 509},

    # Factor used for the delay between two attempts of a request
    # Between each try, the script will wait for this number of seconds:
    # {factor} * (2 ** ({number of previous retries}))
    # This behavior is based on the Retry class of urllib3:
    # https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html#urllib3.util.Retry
    'RETRY_DELAY_FACTOR': 1,

    # Check server SSL(TLS) certificate
    'VERIFY_SSL': False,

    # API requests max duration in seconds
    'TIMEOUT': 10,

    # Proxies for API requests
    # To use system proxies: None (proxies should be set in environment)
    # To disable proxies: {'http': '', 'https': ''}
    # To use a proxy: {'http': 'http://10.10.1.10:3128', 'https': 'http://10.10.1.10:1080'}
    'PROXIES': None,

    # Chunk size for downloads (in bytes)
    'DOWNLOAD_CHUNK_SIZE': 26214400,

    # Chunk size for uploads (in bytes)
    'UPLOAD_CHUNK_SIZE': 26214400,

    # Maximum number of files per request
    'UPLOAD_MAX_FILES': 100,
}
