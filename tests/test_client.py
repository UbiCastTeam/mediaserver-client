import json
from unittest.mock import patch

CONFIG = {
    'SERVER_URL': 'https://msctest',
    'USE_SESSION': False,
}


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.text = json.dumps(json_data)
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    if kwargs['url'] == CONFIG['SERVER_URL'] + '/api/v2/':
        return MockResponse({'mediaserver': '11.0.0', 'success': True}, 200)

    return MockResponse(None, 404)


@patch('requests.get', side_effect=mocked_requests_get)
def test_client(mock_get):
    from ms_client.client import MediaServerClient
    msc = MediaServerClient(local_conf=CONFIG)
    response = msc.api('/')
    assert isinstance(response, dict)
    assert response['mediaserver'] == '11.0.0'

    assert len(mock_get.call_args_list) == 1
