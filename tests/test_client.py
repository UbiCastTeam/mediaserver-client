#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
MediaServer client test file.
'''
from unittest.mock import patch
import json
import logging
import os
import sys
import unittest
import urllib3

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
        return MockResponse({'mediaserver': '10.0.0', 'success': True}, 200)

    return MockResponse(None, 404)


class MSClientTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        print('\n\033[96m----- %s.%s -----\033[0m' % (self.__class__.__name__, self._testMethodName))
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)s %(levelname)s %(message)s',
            stream=sys.stdout
        )
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Setup sys path
        sys.path.pop(0)  # Remove current dir
        src_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        sys.path.insert(0, src_dir)

    @patch('requests.get', side_effect=mocked_requests_get)
    def test_client(self, mock_get):
        from ms_client.client import MediaServerClient
        msc = MediaServerClient(local_conf=CONFIG)
        response = msc.api('/')
        self.assertTrue(isinstance(response, dict))
        self.assertEqual(response['mediaserver'], '10.0.0')

        self.assertEqual(len(mock_get.call_args_list), 1)


if __name__ == '__main__':
    unittest.main()
