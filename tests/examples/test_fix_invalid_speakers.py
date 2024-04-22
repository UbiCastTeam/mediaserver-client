from pathlib import Path
from unittest import mock

import pytest

from examples.fix_invalid_speakers import fix_invalid_speakers


@pytest.fixture(autouse=True)
def no_prompt():
    with mock.patch('examples.fix_invalid_speakers.input', return_value='y') as mock_input:
        yield mock_input


@pytest.fixture()
def csv_path() -> Path:
    path = Path('./tests/examples/fix_invalid_speakers_csv_test_file.csv')
    path.unlink(missing_ok=True)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture()
def catalog():
    return {
        'channels': [
            {
                'oid': 'channel_1',
                'default_settings': {
                    # Invalid email (invalid_1@example.com)
                    'speaker_email': 'user_1@example.com|user_2@example.com|invalid_1@example.com',
                    'speaker_id': 'user_1|user_2|invalid',  # OK
                    'speaker': 'user one|user two|invalid',  # OK
                }
            },
        ],
        'videos': [
            {
                'oid': 'video_1',
                'speaker_email': 'user_1@example.com|user_2@example.com',  # OK
                'speaker_id': 'user_1|UsEr_TwO',  # Multiple ID (UsEr_TwO)
                'speaker': 'user one|user two',  # OK
            },
            {
                'oid': 'video_2',
                'speaker_email': 'user_2@example.com|user_3@example.com',  # OK
                'speaker_id': 'user_2|UsEr_thRee',  # Invalid ID (UsEr_thRee)
                'speaker': 'user two|user 3',  # Invalid name (user 3)
            },
        ],
        'lives': [
            {
                'oid': 'live_1',
                # Invalid email (invalid_2@example.com)
                'speaker_email': 'user_2@example.com|invalid_2@example.com',
                'speaker_id': 'user_2|invalid',  # OK
                'speaker': 'user 2|invalid',  # Multiple name (user 2)
            },
        ],
    }


@pytest.fixture()
def users():
    return [
        {
            'email': 'user_1@example.com',
            'speaker_id': 'user_1',
            'first_name': 'user',
            'last_name': 'one',
        },
        {
            'email': 'user_2@example.com',
            'speaker_id': 'user_2',
            'first_name': 'user',
            'last_name': 'two',
        },
        {
            'email': 'user_3@example.com',
            'speaker_id': 'user_3',
            'first_name': 'user',
            'last_name': 'three',
        },
    ]


@pytest.fixture()
def api_client(catalog, users):
    def mock_api_call(url, **kwargs):
        if url == 'catalog/get-all/':
            return catalog
        elif url == 'users/':
            if kwargs.get('params', {}).get('offset', 0) == 0:
                return {'users': users}
            else:
                return {'users': []}
        elif url == 'settings/defaults/metadata/edit/':
            return {'success': True}
        elif url == 'medias/edit/':
            return {'success': True}

    from ms_client.client import MediaServerClient

    client = MediaServerClient()
    client._server_version = (12, 3, 0)
    client.api = mock.MagicMock(side_effect=mock_api_call)
    with mock.patch('examples.fix_invalid_speakers.MediaServerClient', return_value=client):
        yield client


def test_list_invalid_speakers(api_client, csv_path):
    assert not csv_path.exists()
    fix_invalid_speakers([
        '--conf=./conf.json',
        '--action=list',
        f'--csv-file={csv_path}',
        '--log-level=info',
    ])

    # Check api calls and deleted oids
    assert api_client.api.call_count == 2
    assert api_client.api.call_args_list[0] == mock.call(
        'catalog/get-all/',
        params={'format': 'json'},
        parse_json=True,
        timeout=120
    )
    assert api_client.api.call_args_list[1] == mock.call(
        'users/',
        params={'limit': 500, 'offset': 0}
    )

    # Check output
    assert csv_path.exists()
    csv_lines = [line for line in csv_path.read_text().split('\n') if line]
    assert len(csv_lines) == 5
    assert csv_lines[0] == 'email,ids,names,url,reasons,corrected_email,corrected_id,corrected_name'
    assert set(csv_lines[1:]) == {
        'user_2@example.com,"UsEr_TwO, user_2","user 2, user two",'
        'https://mediaserver/permalink/live_1/,"MULTIPLE_ID, MULTIPLE_NAME",,,',
        'user_3@example.com,UsEr_thRee,user 3,'
        'https://mediaserver/permalink/video_2/,"INVALID_ID, INVALID_NAME",,,',
        'invalid_1@example.com,invalid,invalid,'
        'https://mediaserver/permalink/channel_1/,INVALID_EMAIL,,,',
        'invalid_2@example.com,invalid,invalid,'
        'https://mediaserver/permalink/live_1/,INVALID_EMAIL,,,',
    }


@pytest.mark.parametrize('apply', [True, False])
def test_fix_invalid_speakers(api_client, csv_path, apply):
    # Generate CSV file with corrections
    assert not csv_path.exists()
    csv_path.write_text('\n'.join([
        'email,ids,names,url,reasons,corrected_email,corrected_id,corrected_name',
        (
            'user_2@example.com,"UsEr_TwO, user_2","user 2, user two",'
            'https://mediaserver/permalink/live_1/,"MULTIPLE_ID, MULTIPLE_NAME",'
            ',user_2,user two'
        ),
        (
            'user_3@example.com,UsEr_thRee,user 3,'
            'https://mediaserver/permalink/video_2/,"INVALID_ID, INVALID_NAME",'
            ',user_3,user three'
        ),
        (
            'invalid_1@example.com,invalid,invalid,'
            'https://mediaserver/permalink/channel_1/,INVALID_EMAIL,valid_user@example.com,'
            'valid_user,valid user'
        ),
        (
            'invalid_2@example.com,invalid,invalid,'
            'https://mediaserver/permalink/live_1/,INVALID_EMAIL,'
            'DELETE,DELETE,DELETE'
        ),
    ]))

    # Apply corrections to Mediaserver
    fix_invalid_speakers([
        '--conf=./conf.json',
        '--action=fix',
        f'--csv-file={csv_path}',
        *(('--apply',) if apply else ()),
        '--log-level=info',
    ])

    # Check api calls and deleted oids
    assert api_client.api.call_count == (5 if apply else 1)
    assert api_client.api.call_args_list[0] == mock.call(
        'catalog/get-all/',
        params={'format': 'json'},
        parse_json=True,
        timeout=120
    )
    if apply:
        assert api_client.api.call_args_list[1] == mock.call(
            'settings/defaults/metadata/edit/',
            method='post',
            data={
                'channel_oid': 'channel_1',
                'speaker_email': 'user_1@example.com|user_2@example.com|valid_user@example.com',
                'speaker_id': 'user_1|user_2|valid_user',
                'speaker': 'user one|user two|valid user',
            }
        )
        assert api_client.api.call_args_list[2] == mock.call(
            'medias/edit/',
            method='post',
            data={
                'oid': 'video_1',
                'speaker_email': 'user_1@example.com|user_2@example.com',
                'speaker_id': 'user_1|user_2',
                'speaker': 'user one|user two',
            }
        )
        assert api_client.api.call_args_list[3] == mock.call(
            'medias/edit/',
            method='post',
            data={
                'oid': 'video_2',
                'speaker_email': 'user_2@example.com|user_3@example.com',
                'speaker_id': 'user_2|user_3',
                'speaker': 'user two|user three',
            }
        )
        assert api_client.api.call_args_list[4] == mock.call(
            'medias/edit/',
            method='post',
            data={
                'oid': 'live_1',
                'speaker_email': 'user_2@example.com',
                'speaker_id': 'user_2',
                'speaker': 'user two',
            }
        )
