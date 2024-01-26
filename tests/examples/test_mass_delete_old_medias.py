import smtplib
from collections import namedtuple
from datetime import date, timedelta
from unittest import mock

import pytest


from examples.mass_delete_old_medias import delete_old_medias


TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
IN_A_MONTH = TODAY + timedelta(days=30)
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
        'channels': [],
        'videos': [
            {
                'oid': 'two_years_ago',
                'title': 'Two Years Ago',
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
                'add_date': FOUR_YEARS_AGO.strftime('%Y-%m-%d 20:00:00'),
                'categories': '',
                'storage_used': 30 * 1024 ** 3,  # 30 GB
                'views_last_year': 75,
                'views_last_month': 1,
                'speaker_email': 'john.doe@example.com',
            },
            {
                'oid': 'five_years_ago',
                'title': 'Five Years Ago',
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
        }
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
        elif url == 'users/':
            if kwargs.get('params', {}).get('offset', 0) == 0:
                return {'users': users}
            else:
                return {'users': []}

    from ms_client.client import MediaServerClient

    client = MediaServerClient()
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
    with mock.patch('smtplib.SMTP_SSL', autospec=True, return_value=mock_smtp):
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
    ]
)
def test_delete_old_medias(
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
        ('--apply' if apply else ''),
        '--log-level=info',
    ])

    # Check mails
    assert len(mock_smtp.mailbox) == len(expected_sent_mails)
    for recipient, oids in expected_sent_mails:
        assert mock_smtp.has_mail('sender@example.com', recipient, oids)

    # Check api calls and deleted oids
    assert api_client.api.call_count == 2 if expected_deleted_oids else 1
    assert api_client.api.call_args_list[0] == mock.call(
        'catalog/get-all/',
        params={'format': 'flat', 'timings': 'yes'}
    )
    if expected_deleted_oids:
        assert api_client.api.call_args_list[1] == mock.call(
            'catalog/bulk_delete/',
            method='post',
            data=dict(oids=expected_deleted_oids)
        )
