import sys
from pathlib import Path

import urllib3

import pytest


@pytest.fixture(scope='session', autouse=True)
def disable_urllib3_warnings():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture(scope='session', autouse=True)
def add_client_to_path():
    path = Path(__file__).resolve().parent.parent
    sys.path.pop(0)  # Remove current dir
    sys.path.insert(0, str(path))
