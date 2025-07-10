import smtplib
from collections import namedtuple
from datetime import date, timedelta
from unittest import mock

import pytest


from examples.mass_delete_old_medias import delete_old_medias, MisconfiguredError


TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
IN_A_MONTH = TODAY + timedelta(days=30)
ONE_YEAR_AGO = TODAY - timedelta(days=365)
TWO_YEARS_AGO = TODAY - timedelta(days=365 * 2)
THREE_YEARS_AGO = TODAY - timedelta(days=365 * 3)
FOUR_YEARS_AGO = TODAY - timedelta(days=365 * 4)
FIVE_YEARS_AGO = TODAY - timedelta(days=365 * 5)


@pytest.fixture(autouse=True)
def no_prompt():
    with mock.patch('examples.mass_delete_old_medias.input', return_value='y') as mock_input:
        yield mock_input


@pytest.fixture()
def catalog():
    return {
        'channels': [
            {
                'oid': 'channel_1',
                'managers_emails': 'manager@example.com\n#manager_inactive@example.com\nmanager_invalid@example.com',
            },
            {
                'oid': 'channel_2',
                'managers_emails': '',
            },
        ],
        'videos': [
            {
                'oid': 'two_years_ago',
                'title': 'Two Years Ago',
                'parent_oid': 'channel_1',
                'add_date': TWO_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': '',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': 'john.doe@example.com',
            },
            {
                'oid': 'three_years_ago_no_speaker',
                'title': 'Three Years Ago: no speaker',
                'parent_oid': 'channel_1',
                'add_date': THREE_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': '',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': '',
            },
            {
                'oid': 'three_years_ago_dnd',
                'title': 'Three Years Ago: do not delete',
                'parent_oid': 'channel_1',
                'add_date': THREE_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': 'do not delete',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': '',
            },
            {
                'oid': 'three_years_ago_mail_error',
                'title': 'Three Years Ago: mail error',
                'parent_oid': 'channel_2',
                'add_date': THREE_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': '',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': 'error@example.com',
            },
            {
                'oid': 'four_years_ago',
                'title': 'Four Years Ago',
                'parent_oid': 'channel_1',
                'add_date': FOUR_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': 'some_category',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': 'john.doe@example.com',
            },
            {
                'oid': 'five_years_ago',
                'title': 'Five Years Ago',
                'parent_oid': 'channel_1',
                'add_date': FIVE_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': '',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': 'john.doe@example.com | jane.doe@example.com',
            },
        ],
        'lives': [
            {
                'oid': 'live_three_years_ago',
                'title': 'Live: Three Years Ago',
                'parent_oid': 'channel_1',
                'add_date': THREE_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': '',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': 'john.doe@example.com |  | inactive@example.com | deleted@example.com',
                'speaker_id': 'john.doe | june.doe |  | ',
            },
        ],
    }


@pytest.fixture()
def users():
    return [
        {
            'email': 'john.doe@example.com',
            'is_active': True,
            'speaker_id': '',
        },
        {
            'email': 'jane.doe@example.com',
            'is_active': True,
            'speaker_id': '',
        },
        {
            'email': 'june.doe@example.com',
            'is_active': True,
            'speaker_id': 'june.doe',
        },
        {
            'email': 'inactive@example.com',
            'is_active': False,
            'speaker_id': '',
        },
        {
            'email': 'manager@example.com',
            'is_active': True,
            'speaker_id': '',
        },
    ]


@pytest.fixture()
def api_client(catalog, users):
    def mock_api_call(url, **kwargs):
        if url == 'catalog/bulk_delete/':
            return {
                'statuses': {oid: {'status': 200} for oid in kwargs['data']['oids']}
            }
        elif url == 'catalog/get-all/':
            return catalog
        elif url == 'stats/unwatched/':
            return {
                'success': True,
                'start_date': kwargs['params']['sd'],
                'end_date': kwargs['params']['ed'],
                'unwatched': [
                    {
                        'object_id': 'three_years_ago_no_speaker',
                        'views_over_period': 0,
                    },
                    {
                        'object_id': 'three_years_ago_dnd',
                        'views_over_period': 0,
                    },
                    {
                        'object_id': 'three_years_ago_mail_error',
                        'views_over_period': 0,
                    },
                ],
            }
        elif url == 'users/':
            if kwargs.get('params', {}).get('offset', 0) == 0:
                return {'users': users}
            else:
                return {'users': []}
        elif url == 'info/':
            return {"data": {"trash_enabled": True}}

    from ms_client.client import MediaServerClient

    client = MediaServerClient()
    client._server_version = (12, 3, 0)
    client.conf['SMTP_SERVER'] = 'smtp.example.com'
    client.conf['SMTP_LOGIN'] = 'sender'
    client.conf['SMTP_PASSWORD'] = 's3cr3t'
    client.conf['SMTP_SENDER_EMAIL'] = 'sender@example.com'
    client.api = mock.MagicMock(side_effect=mock_api_call)
    with mock.patch('examples.mass_delete_old_medias.MediaServerClient', return_value=client):
        yield client


Message = namedtuple('Message', ['sender', 'recipient', 'message'])


class MockSMTP:
    def __init__(self):
        self._logged_in = False
        self.mailbox: list[Message] = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        pass

    def login(self, sender, password):
        assert sender == 'sender'
        assert password == 's3cr3t'
        self._logged_in = True

    def starttls(self, context):
        pass

    def quit(self):
        pass

    def sendmail(self, sender, recipient, message):
        assert self._logged_in
        if recipient == 'error@example.com':
            raise smtplib.SMTPRecipientsRefused({'error@example.com': (550, b'User unknown')})
        self.mailbox.append(Message(sender, recipient, message))

    def has_mail(self, sender_address: str, recipient: str, oids: list[str]):
        for mail in self.mailbox:
            if (
                mail.sender == sender_address
                and mail.recipient == recipient
                and all((oid in mail.message) for oid in oids)
            ):
                return True
        return False


@pytest.fixture()
def mock_smtp():
    mock_smtp = MockSMTP()
    with mock.patch('smtplib.SMTP', autospec=True, return_value=mock_smtp):
        yield mock_smtp


@pytest.mark.parametrize(
    'delete_date, added_before, skip_category, apply,'
    'expected_sent_mails, expected_deleted_oids', [
        pytest.param(
            IN_A_MONTH, TWO_YEARS_AGO, 'do not delete', True,
            [
                ('fallback@example.com', [
                    'three_years_ago_no_speaker', 'three_years_ago_mail_error']),
                ('john.doe@example.com', [
                    'four_years_ago', 'five_years_ago', 'live_three_years_ago']),
                ('jane.doe@example.com', ['five_years_ago']),
                ('june.doe@example.com', ['live_three_years_ago']),
            ], [], id='First notification'
        ),
        pytest.param(
            IN_A_MONTH, TWO_YEARS_AGO, 'do not delete', False,
            [], [], id='First notification - dry-run'
        ),
        pytest.param(
            TOMORROW, TWO_YEARS_AGO, 'do not delete', True,
            [
                ('fallback@example.com', [
                    'three_years_ago_no_speaker', 'three_years_ago_mail_error']),
                ('john.doe@example.com', [
                    'four_years_ago', 'five_years_ago', 'live_three_years_ago']),
                ('jane.doe@example.com', ['five_years_ago']),
                ('june.doe@example.com', ['live_three_years_ago']),
            ], [], id='Second notification'
        ),
        pytest.param(
            TODAY, TWO_YEARS_AGO, 'do not delete', True,
            [], [
                'three_years_ago_no_speaker', 'three_years_ago_mail_error',
                'four_years_ago', 'five_years_ago', 'live_three_years_ago'
            ], id='Deletion'
        ),
        pytest.param(
            TODAY, TWO_YEARS_AGO, 'do not delete', False,
            [], [], id='Deletion - dry-run'
        ),
    ]
)
def test_delete_old_medias__full_workflow(
    api_client, mock_smtp,
    delete_date, added_before, skip_category, apply,
    expected_sent_mails, expected_deleted_oids,
):
    delete_old_medias([
        '--conf=./conf.json',
        f'--delete-date={delete_date.strftime("%Y-%m-%d")}',
        f'--added-before={added_before.strftime("%Y-%m-%d")}',
        f'--skip-category={skip_category}',
        '--fallback-email=fallback@example.com',
        *(('--apply',) if apply else ()),
        '--log-level=info',
    ])

    # Check mails
    assert len(mock_smtp.mailbox) == len(expected_sent_mails)
    for recipient, oids in expected_sent_mails:
        assert mock_smtp.has_mail('sender@example.com', recipient, oids)

    if apply:
        assert api_client.api.call_args_list.pop(0) == mock.call('info/')

    # Check api calls and deleted oids
    assert api_client.api.call_count == 3 if expected_deleted_oids else 2
    assert api_client.api.call_args_list.pop(0) == mock.call(
        'catalog/get-all/',
        params={'format': 'json'},
        parse_json=True,
        timeout=120
    )
    if expected_deleted_oids:
        assert api_client.api.call_args_list.pop(0) == mock.call(
            'catalog/bulk_delete/',
            method='post',
            data=dict(oids=expected_deleted_oids)
        )


@pytest.mark.parametrize(
    'added_after, added_before, skip_categories,'
    'views_max_count, views_playback_threshold, views_after, views_before,'
    'expected_deleted_oids', [
        pytest.param(
            FOUR_YEARS_AGO, TWO_YEARS_AGO, ['do not delete'],
            None, None, None, None,
            [
                'three_years_ago_no_speaker',
                'three_years_ago_mail_error',
                'four_years_ago',
                'live_three_years_ago',
            ], id='Filter by added date'
        ),
        pytest.param(
            FOUR_YEARS_AGO, TWO_YEARS_AGO, ['do not delete', 'some_category'],
            None, None, None, None,
            [
                'three_years_ago_no_speaker',
                'three_years_ago_mail_error',
                'live_three_years_ago',
            ], id='Filter by added date and multiple category'
        ),
        pytest.param(
            None, None, ['do not delete', 'some_category'],
            1, 5, TWO_YEARS_AGO, ONE_YEAR_AGO,
            [
                'three_years_ago_no_speaker',
                'three_years_ago_mail_error',
            ], id='Filter by views count'
        ),
        pytest.param(
            None, None, ['do not delete', 'some_category'],
            1, 5, THREE_YEARS_AGO, TWO_YEARS_AGO,
            [], id='Filter by views eliminates media created after beginning of view period'
        ),
    ]
)
def test_delete_old_medias__selection_filters(
    api_client,
    added_after, added_before, skip_categories,
    views_max_count, views_playback_threshold, views_after, views_before,
    expected_deleted_oids,
):
    params = [
        '--conf=./conf.json',
        f'--delete-date={TODAY.strftime("%Y-%m-%d")}',
        '--fallback-email=fallback@example.com',
        '--apply',
        '--log-level=debug',
    ]
    if added_after is not None:
        params.append(f'--added-after={added_after.strftime("%Y-%m-%d")}')
    if added_before is not None:
        params.append(f'--added-before={added_before.strftime("%Y-%m-%d")}')
    if skip_categories is not None:
        params += [f'--skip-category={skip_category}' for skip_category in skip_categories]
    if views_max_count is not None:
        params.append(f'--views-max-count={views_max_count}')
    if views_playback_threshold is not None:
        params.append(f'--views-playback-threshold={views_playback_threshold}')
    if views_after is not None:
        params.append(f'--views-after={views_after.strftime("%Y-%m-%d")}')
    if views_before is not None:
        params.append(f'--views-before={views_before.strftime("%Y-%m-%d")}')

    delete_old_medias(params)

    api_calls = iter(api_client.api.call_args_list)

    assert next(api_calls) == mock.call('info/')

    assert next(api_calls) == mock.call(
        'catalog/get-all/',
        params={'format': 'json'},
        parse_json=True,
        timeout=120
    )

    if views_max_count:
        assert next(api_calls) == mock.call(
            'stats/unwatched/',
            params={
                'playback_threshold': views_playback_threshold,
                'views_threshold': views_max_count,
                'recursive': 'yes',
                'sd': views_after.strftime('%Y-%m-%d'),
                'ed': views_before.strftime('%Y-%m-%d'),
            },
        )

    if expected_deleted_oids:
        assert next(api_calls) == mock.call(
            'catalog/bulk_delete/',
            method='post',
            data=dict(oids=expected_deleted_oids)
        )


@pytest.mark.parametrize(
    'delete_date, send_email_on_deletion, fallback_to_channel_manager, apply, expected_sent_mails', [
        pytest.param(
            IN_A_MONTH, False, False, True,
            [
                ('fallback@example.com', ['three_years_ago_no_speaker', 'three_years_ago_mail_error']),
                ('john.doe@example.com', ['four_years_ago', 'live_three_years_ago']),
                ('june.doe@example.com', ['live_three_years_ago']),
            ], id='First notification'
        ),
        pytest.param(
            IN_A_MONTH, False, True, True,
            [
                ('manager@example.com', ['three_years_ago_no_speaker']),
                ('fallback@example.com', ['three_years_ago_mail_error']),
                ('john.doe@example.com', ['four_years_ago', 'live_three_years_ago']),
                ('june.doe@example.com', ['live_three_years_ago']),
            ], id='First notification - fallback on channel_manager'
        ),
        pytest.param(
            IN_A_MONTH, False, False, False,
            [], id='First notification - dry-run'
        ),
        pytest.param(
            TODAY, False, False, True,
            [], id='Deletion - no mails on deletion'
        ),
        pytest.param(
            TODAY, True, False, True,
            [
                ('fallback@example.com', ['three_years_ago_no_speaker', 'three_years_ago_mail_error']),
                ('john.doe@example.com', ['four_years_ago', 'live_three_years_ago']),
                ('june.doe@example.com', ['live_three_years_ago']),
            ], id='Deletion - send mails on deletion'
        ),
        pytest.param(
            TODAY, True, False, False,
            [], id='Deletion - send mails on deletion - dry-run'
        ),
    ]
)
@pytest.mark.usefixtures('api_client')
def test_delete_old_medias__mailing_behaviour(
    mock_smtp,
    delete_date, send_email_on_deletion, fallback_to_channel_manager, apply,
    expected_sent_mails,
):
    delete_old_medias([
        '--conf=./conf.json',
        f'--delete-date={delete_date.strftime("%Y-%m-%d")}',
        f'--added-after={FOUR_YEARS_AGO.strftime("%Y-%m-%d")}',
        f'--added-before={TWO_YEARS_AGO.strftime("%Y-%m-%d")}',
        '--skip-category="do not delete"',
        '--fallback-email=fallback@example.com',
        *(('--send-email-on-deletion',) if send_email_on_deletion else ()),
        *(('--fallback-to-channel-manager',) if fallback_to_channel_manager else ()),
        *(('--apply',) if apply else ()),
        '--log-level=info',
    ])

    # Check mails
    assert len(mock_smtp.mailbox) == len(expected_sent_mails)
    for recipient, oids in expected_sent_mails:
        assert mock_smtp.has_mail('sender@example.com', recipient, oids)


@pytest.mark.parametrize(
    'added_after, added_before, views_max_count, views_after, views_before', [
        pytest.param(
            None, None, None, None, None,
            id='No filters'
        ),
        pytest.param(
            None, None, 3, None, None,
            id='No views period'
        ),
        pytest.param(
            None, None, 3, THREE_YEARS_AGO, None,
            id='Incomplete views period - start only'
        ),
        pytest.param(
            None, None, 3, None, TWO_YEARS_AGO,
            id='Incomplete views period - end only'
        ),
        pytest.param(
            None, None, 3, ONE_YEAR_AGO, TODAY,
            id='Views period crosses today'
        ),
        pytest.param(
            None, None, -3, THREE_YEARS_AGO, ONE_YEAR_AGO,
            id='Negative views count'
        ),
    ]
)
@pytest.mark.usefixtures('api_client')
def test_delete_old_medias__misconfigured(
    added_after, added_before, views_max_count, views_after, views_before,
):
    params = [
        '--conf=./conf.json',
        f'--delete-date={TODAY.strftime("%Y-%m-%d")}',
        '--fallback-email=fallback@example.com',
        '--apply',
        '--log-level=debug',
    ]
    if added_after is not None:
        params.append(f'--added-after={added_after.strftime("%Y-%m-%d")}')
    if added_before is not None:
        params.append(f'--added-before={added_before.strftime("%Y-%m-%d")}')
    if views_max_count is not None:
        params.append(f'--views-max-count={views_max_count}')
    if views_after is not None:
        params.append(f'--views-after={views_after.strftime("%Y-%m-%d")}')
    if views_before is not None:
        params.append(f'--views-before={views_before.strftime("%Y-%m-%d")}')

    with pytest.raises(MisconfiguredError):
        delete_old_medias(params)
