import pytest

from ms_client.lib import utils

OID_PART = '123456789abcdefghij'


@pytest.mark.parametrize('item, expected', [
    pytest.param({'oid': f'v{OID_PART}', 'title': 'the title'}, 'video $oid "the title"', id='no change'),
    pytest.param({'oid': f'v{OID_PART}', 'title': ''}, 'video $oid', id='empty media'),
    pytest.param({'oid': f'c{OID_PART}', 'title': ''}, 'channel $oid', id='empty channel'),
    pytest.param({'oid': f'v{OID_PART}', 'title': 'the/title'}, 'video $oid "the/title"', id='with slash'),
    pytest.param({'oid': f'v{OID_PART}', 'title': '-the title'}, 'video $oid "-the title"', id='starting with -'),
    pytest.param({'oid': f'v{OID_PART}', 'title': 'a' * 100}, 'video $oid "' + 'a' * 57 + '..."', id='too long'),
    pytest.param({'oid': f'v{OID_PART}', 'title': '*' * 100}, 'video $oid "' + '*' * 57 + '..."', id='only stars'),
])
def test_item_repr(item, expected):
    assert utils.format_item(item) == expected.replace('$oid', item['oid'])


@pytest.mark.parametrize('item, expected', [
    pytest.param({'oid': f'v{OID_PART}', 'title': 'the title'}, 'the title - $oid', id='no change'),
    pytest.param({'oid': f'v{OID_PART}', 'title': ''}, 'media - $oid', id='empty media'),
    pytest.param({'oid': f'c{OID_PART}', 'title': ''}, 'channel - $oid', id='empty channel'),
    pytest.param({'oid': f'v{OID_PART}', 'title': 'the/title'}, 'the title - $oid', id='with slash'),
    pytest.param({'oid': f'v{OID_PART}', 'title': '-the title'}, 'the title - $oid', id='starting with -'),
    pytest.param({'oid': f'v{OID_PART}', 'title': 'a' * 100}, 'a' * 54 + '... - $oid', id='too long'),
    pytest.param({'oid': f'v{OID_PART}', 'title': '*' * 100}, 'media - $oid', id='only stars'),
])
def test_item_file_name(item, expected):
    assert utils.format_item_file(item) == expected.replace('$oid', item['oid'])
