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

    # Use a persistent session for requests
    'USE_SESSION': True,

    # Check server SSL(TLS) certificate
    'VERIFY_SSL': False,

    # API requests max duration in seconds
    'TIMEOUT': 10,

    # Proxies for API requests
    # Set this to `null` to use your system default value
    # Example: {'http': 'http://10.10.1.10:3128', 'https': 'http://10.10.1.10:1080'}
    'PROXIES': {'http': '', 'https': ''},

    # Chunk size for uploads
    'UPLOAD_CHUNK_SIZE': 5242880,
}
