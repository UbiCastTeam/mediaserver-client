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
    'CLIENT_ID': 'python-api-client',

    # Language for API messages
    # Use None to use MediaServer default language
    # Supported languages are 'en' or 'fr'.
    'LANGUAGE': 'en',

    # Use a persistent session for requests
    'USE_SESSION': True,

    # If failures should be auto-retried N times
    # disabled by default
    'MAX_RETRY': None,

    # List of status codes that should not trigger a retry
    'RETRY_EXCEPT': [403, 404],

    # Check server SSL(TLS) certificate
    'VERIFY_SSL': False,

    # API requests max duration in seconds
    'TIMEOUT': 10,

    # Proxies for API requests
    # To use system proxies: None (proxies should be set in environment)
    # To disable proxies: {'http': '', 'https': ''}
    # To use a proxy: {'http': 'http://10.10.1.10:3128', 'https': 'http://10.10.1.10:1080'}
    'PROXIES': None,

    # Chunk size for uploads
    'UPLOAD_CHUNK_SIZE': 5242880,
}
