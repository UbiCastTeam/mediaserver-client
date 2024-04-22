import json
from itertools import count
from unittest.mock import patch

import pytest


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


@pytest.fixture
def catalog():
    counter = count(1)
    return {
        "channels": [
            {
                "oid": "c0001stlevelempty",
                "dbid": next(counter),
                "title": "First level empty Last Year",
                "add_date": "2023-07-03 16:24:00",
                "parent_oid": None,
            },
            {
                "oid": "c0001stlevelfull",
                "dbid": next(counter),
                "title": "First level empty Last Year",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": None,
            },
            {
                "oid": "c0001stlevelfull3sub",
                "dbid": next(counter),
                "title": "First level full with 3 subchannels",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": None,
            },
            {
                "oid": "c0002ndlevelempty",
                "dbid": next(counter),
                "title": "Second level empty",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": "c0001stlevelfull3sub",
            },
            {
                "oid": "c0002ndlevelfull",
                "dbid": next(counter),
                "title": "Second level full",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": "c0001stlevelfull3sub",
            },
            {
                "oid": "c0002ndlevelfull3sub",
                "dbid": next(counter),
                "title": "Second level full with 3 subchannels",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": "c0001stlevelfull3sub",
            },
            {
                "oid": "c0003rdlevelempty",
                "dbid": next(counter),
                "title": "Third level empty",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": "c0002ndlevelfull3sub",
            },
            {
                "oid": "c0003rdlevelempty2",
                "dbid": next(counter),
                "title": "Third level second empty",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": "c0002ndlevelfull3sub",
            },
            {
                "oid": "c0003rdlevelfull2sub",
                "dbid": next(counter),
                "title": "Third level full with 2 subchannels",
                "add_date": "2022-07-03 16:24:00",
                "parent_oid": "c0002ndlevelfull3sub",
            },
            {
                "oid": "c0004thlevelempty",
                "dbid": next(counter),
                "title": "Fourth level empty",
                "add_date": "2023-07-03 16:24:00",
                "parent_oid": "c0003rdlevelfull2sub",
            },
            {
                "oid": "c0004thlevelfull3sub",
                "dbid": next(counter),
                "title": "Fourth level full with 3 subchannels",
                "add_date": "2023-07-03 16:24:00",
                "parent_oid": "c0003rdlevelfull2sub",
            },
            {
                "oid": "c0005thlevelempty",
                "dbid": next(counter),
                "title": "Fifth level empty",
                "add_date": "2023-07-03 16:24:00",
                "parent_oid": "c0004thlevelfull3sub",
            },
            {
                "oid": "c0005thlevelemptysubchannel",
                "dbid": next(counter),
                "title": "Fifth level with empty subchannel",
                "add_date": "2023-07-03 16:24:00",
                "parent_oid": "c0004thlevelfull3sub",
            },
            {
                "oid": "c0006thlevelempty",
                "dbid": next(counter),
                "title": "Sixth level empty",
                "add_date": "2023-07-03 16:24:00",
                "parent_oid": "c0005thlevelemptysubchannel",
            },
        ],
        "videos": [
            {"parent_oid": "c0001stlevelfull"},
            {"parent_oid": "c0001stlevelfull"},
            {"parent_oid": "c0001stlevelfull"},
            {"parent_oid": "c0002ndlevelfull"},
            {"parent_oid": "c0002ndlevelfull"},
            {"parent_oid": "c0002ndlevelfull"},
            {"parent_oid": "c0002ndlevelfull3sub"},
            {"parent_oid": "c0002ndlevelfull3sub"},
            {"parent_oid": "c0002ndlevelfull3sub"},
        ],
        "lives": [
            {"parent_oid": "c0001stlevelfull"},
        ],
        "photos": [
            {"parent_oid": "c0001stlevelfull"},
        ],
    }


@pytest.fixture()
def api_client(catalog):
    def mock_api_call(url, **kwargs):
        if url == 'catalog/get-all/':
            return catalog

    from ms_client.client import MediaServerClient
    client = MediaServerClient()
    client._server_version = (12, 3, 0)
    client.api = mock_api_call
    return client


def test_get_catalog__flat(api_client, catalog):
    response = api_client.get_catalog(fmt='flat')
    assert response == catalog


def test_get_catalog__tree(api_client, catalog):
    response = api_client.get_catalog(fmt='tree')
    assert response == {
        "channels": [
            {
                "oid": "c0001stlevelempty",
                "dbid": 1,
                "title": "First level empty Last Year",
                "parent_oid": None,
                "add_date": "2023-07-03 16:24:00",
            },
            {
                "oid": "c0001stlevelfull",
                "dbid": 2,
                "title": "First level empty Last Year",
                "parent_oid": None,
                "add_date": "2022-07-03 16:24:00",
                "videos": [
                    {"parent_oid": "c0001stlevelfull"},
                    {"parent_oid": "c0001stlevelfull"},
                    {"parent_oid": "c0001stlevelfull"},
                ],
                "lives": [{"parent_oid": "c0001stlevelfull"}],
                "photos": [{"parent_oid": "c0001stlevelfull"}],
            },
            {
                "oid": "c0001stlevelfull3sub",
                "dbid": 3,
                "title": "First level full with 3 subchannels",
                "parent_oid": None,
                "add_date": "2022-07-03 16:24:00",
                "channels": [
                    {
                        "oid": "c0002ndlevelempty",
                        "dbid": 4,
                        "title": "Second level empty",
                        "parent_oid": "c0001stlevelfull3sub",
                        "add_date": "2022-07-03 16:24:00",
                    },
                    {
                        "oid": "c0002ndlevelfull",
                        "dbid": 5,
                        "title": "Second level full",
                        "parent_oid": "c0001stlevelfull3sub",
                        "add_date": "2022-07-03 16:24:00",
                        "videos": [
                            {"parent_oid": "c0002ndlevelfull"},
                            {"parent_oid": "c0002ndlevelfull"},
                            {"parent_oid": "c0002ndlevelfull"},
                        ],
                    },
                    {
                        "oid": "c0002ndlevelfull3sub",
                        "dbid": 6,
                        "title": "Second level full with 3 subchannels",
                        "parent_oid": "c0001stlevelfull3sub",
                        "add_date": "2022-07-03 16:24:00",
                        "videos": [
                            {"parent_oid": "c0002ndlevelfull3sub"},
                            {"parent_oid": "c0002ndlevelfull3sub"},
                            {"parent_oid": "c0002ndlevelfull3sub"},
                        ],
                        "channels": [
                            {
                                "oid": "c0003rdlevelempty",
                                "dbid": 7,
                                "title": "Third level empty",
                                "parent_oid": "c0002ndlevelfull3sub",
                                "add_date": "2022-07-03 16:24:00",
                            },
                            {
                                "oid": "c0003rdlevelempty2",
                                "dbid": 8,
                                "title": "Third level second empty",
                                "parent_oid": "c0002ndlevelfull3sub",
                                "add_date": "2022-07-03 16:24:00",
                            },
                            {
                                "oid": "c0003rdlevelfull2sub",
                                "dbid": 9,
                                "title": "Third level full with 2 subchannels",
                                "parent_oid": "c0002ndlevelfull3sub",
                                "add_date": "2022-07-03 16:24:00",
                                "channels": [
                                    {
                                        "oid": "c0004thlevelempty",
                                        "dbid": 10,
                                        "title": "Fourth level empty",
                                        "parent_oid": "c0003rdlevelfull2sub",
                                        "add_date": "2023-07-03 16:24:00",
                                    },
                                    {
                                        "oid": "c0004thlevelfull3sub",
                                        "dbid": 11,
                                        "title": "Fourth level full with 3 subchannels",
                                        "parent_oid": "c0003rdlevelfull2sub",
                                        "add_date": "2023-07-03 16:24:00",
                                        "channels": [
                                            {
                                                "oid": "c0005thlevelempty",
                                                "dbid": 12,
                                                "title": "Fifth level empty",
                                                "parent_oid": "c0004thlevelfull3sub",
                                                "add_date": "2023-07-03 16:24:00",
                                            },
                                            {
                                                "oid": "c0005thlevelemptysubchannel",
                                                "dbid": 13,
                                                "title": "Fifth level with empty subchannel",
                                                "parent_oid": "c0004thlevelfull3sub",
                                                "add_date": "2023-07-03 16:24:00",
                                                "channels": [
                                                    {
                                                        "oid": "c0006thlevelempty",
                                                        "dbid": 14,
                                                        "title": "Sixth level empty",
                                                        "parent_oid": "c0005thlevelemptysubchannel",
                                                        "add_date": "2023-07-03 16:24:00",
                                                    },
                                                ],
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }
