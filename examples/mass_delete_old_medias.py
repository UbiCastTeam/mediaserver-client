#!/usr/bin/env python3
"""
Script which aims at freeing storage by deleting medias older than a
given number of days. Depending on the planned deletion date and the
execution date, the script will either delete the medias or email
speakers about the impending deletion, to give them time to protect
their medias by applying a category to them.
"""

import argparse
from contextlib import nullcontext
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itertools import zip_longest
import logging
import os
from pathlib import Path
import smtplib
import ssl
import sys
from typing import Optional
from urllib.parse import urlparse

try:
    from ms_client.client import MediaServerClient
except ModuleNotFoundError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient


logger = logging.getLogger(__name__)
DEFAULT_PLAIN_EMAIL_TEMPLATE = (
    'The following {media_count} medias (total {media_size_pp}) hosted '
    'on the video platform {platform_hostname} should '
    'be deleted according to the University policy. You have until '
    '{delete_date} to review each media below and set the '
    '"{skip_category}" category if you need to preserve this content. '
    'After this date, the media will be deleted. You can also delete it '
    'when you review it.\n\n'
    'List of media to review ({media_count}):\n'
    '{list_of_media}\n'
)
DEFAULT_HTML_EMAIL_TEMPLATE = (
    '<p>The following {media_count} medias (total {media_size_pp}) '
    'hosted on the video platform {platform_hostname} should be deleted '
    'according to the University policy. You have '
    'until {delete_date} to review each media below and set the '
    '"{skip_category}" category if you need to preserve this content. '
    'After this date, the media will be deleted. You can also delete '
    'it when you review it.</p>\n'
    '<p>List of media to review ({media_count}):</p>\n'
    '<ul>{list_of_media}</ul>\n'
)
DUMMY_MEDIAS = [
    {
        'oid': 'oid_1',
        'title': 'Media #1',
        'storage_used': 10 * 1000 ** 3,  # 10 GB
        'views_last_year': 10,
        'views_last_month': 1,
    },
    {
        'oid': 'oid_2',
        'title': 'Media #2',
        'storage_used': 20 * 1000 ** 3,  # 20 GB
        'views_last_year': 20,
        'views_last_month': 2,
    },
    {
        'oid': 'oid_3',
        'title': 'Media #3',
        'storage_used': 30 * 1000 ** 3,  # 30 GB
        'views_last_year': 30,
        'views_last_month': 3,
    },
]


class MisconfiguredError(Exception):
    pass


def pp_size(size_bytes: int) -> str:
    """
    Return human-readable size with automatic suffix.
    """
    for unit in ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z'):
        if abs(size_bytes) < 1000:
            return f'{size_bytes:.1f}{unit}B'
        size_bytes /= 1000
    return f'{size_bytes:.1f}YB'


def _get_old_medias(
    msc: MediaServerClient,
    before_date: date,
    skip_category: str,
) -> list[dict]:
    response = msc.api('catalog/get-all/', params={'format': 'flat', 'timings': 'yes'})
    skip_category = skip_category.lower()
    old_medias = []
    for key in ('videos', 'lives', 'photos'):
        medias = response.get(key, ())
        for media in medias:
            add_date = datetime.strptime(media['add_date'], '%Y-%m-%d %H:%M:%S').date()
            categories = {cat.strip(' \r\t').lower() for cat in (media['categories'] or '').split('\n')}
            if add_date < before_date and (not skip_category or skip_category not in categories):
                old_medias.append(media)
            else:
                media_pp = f'{media["title"]} [{media["oid"]}]'
                if add_date >= before_date:
                    before_date_pp = before_date.strftime('%Y-%m-%d')
                    logger.debug(
                        f'{media_pp} was skipped because it was added after {before_date_pp}.'
                    )
                else:
                    logger.debug(
                        f'{media_pp} was skipped because it has the skip_category.'
                    )

    storage_used = sum(media['storage_used'] for media in old_medias)
    logger.info(
        f'Found {len(old_medias)} medias added before {before_date.strftime("%Y-%m-%d")} '
        f'(size: {pp_size(storage_used)}).'
    )
    return old_medias


def _get_users(msc: MediaServerClient, page_size=500):
    users = []
    offset = 0
    response = msc.api('users/', params={'limit': page_size, 'offset': offset})
    while response['users']:
        users += response['users']
        offset += page_size
        response = msc.api('users/', params={'limit': page_size, 'offset': offset})
    return users


def _prepare_mail(
    msc: MediaServerClient,
    sender: str,
    speaker_email: str,
    medias: list[dict],
    delete_date: date,
    skip_category: str,
    html_template: Optional[str],
    plain_template: Optional[str],
    email_subject_template: str,
) -> tuple[str, dict]:
    # Ensure each media is only once in the list.
    medias = list({media['oid']: media for media in medias}.values())

    ms_perma_url = msc.conf['SERVER_URL'] + '/permalink/'
    ms_edit_url = msc.conf['SERVER_URL'] + '/edit/'
    context = {
        'media_count': len(medias),
        'media_size_pp': pp_size(sum(media['storage_used'] for media in medias)),
        'delete_date': delete_date.strftime('%B %d, %Y'),
        'skip_category': skip_category,
        'platform_hostname': urlparse(msc.conf['SERVER_URL']).netloc,
    }
    message = MIMEMultipart('alternative')
    message['Subject'] = email_subject_template.format(**context)
    message['From'] = sender
    message['To'] = speaker_email

    if plain_template:
        plain_media_list = '\n'.join(
            f'\t- {ms_perma_url}{media["oid"]}/ - "{media["title"]}" - '
            f'viewed {media["views_last_year"]} times last year, '
            f'{media["views_last_month"]} times last month '
            f'(click here {ms_edit_url}{media["oid"]}/#id_categories '
            f'to protect against deletion)'
            for media in medias
        )
        plain = plain_template.format(list_of_media=plain_media_list, **context)
        message.attach(MIMEText(plain, 'plain'))
    if html_template:
        html_media_list = '\n'.join(
            f'<li><a href="{ms_perma_url}{media["oid"]}/">"{media["title"]}"</a> '
            f'viewed {media["views_last_year"]} times last year, '
            f'{media["views_last_month"]} times last month '
            f'(click <a href="{ms_edit_url}{media["oid"]}/#id_categories">here</a> '
            f'to protect against deletion)</li>'
            for media in medias
        )
        html = html_template.format(list_of_media=html_media_list, **context)
        message.attach(MIMEText(html, 'html'))
    context['media_oids'] = [media['oid'] for media in medias]
    return message.as_string(), context


def _get_templates(
    html_email_template: Path,
    plain_email_template: Path,
):
    try:
        html_template = html_email_template.read_text()
        html_is_custom = True
    except FileNotFoundError:
        html_template = DEFAULT_HTML_EMAIL_TEMPLATE
        html_is_custom = False
    try:
        plain_template = plain_email_template.read_text()
        plain_is_custom = True
    except FileNotFoundError:
        plain_template = DEFAULT_PLAIN_EMAIL_TEMPLATE
        plain_is_custom = False

    # If only one custom template is given,
    # prioritize it and don't send the default version for the other one.
    if html_is_custom and not plain_is_custom:
        plain_template = None
        logger.info(
            'HTML email template was found but plain email template was not. '
            'Using HTML version only.'
        )
    elif not html_is_custom and plain_is_custom:
        html_template = None
        logger.info(
            'Plain email template was found but HTML email template was not. '
            'Using plain version only.'
        )
    elif not html_is_custom and not plain_is_custom:
        logger.info(
            'Neither HTML nor plain email template were found. '
            'Using default email templates.'
        )
    else:
        logger.info(
            'HTML and plain email template were found. '
            'Using custom email templates.'
        )
    return html_template, plain_template


def _warn_speakers_about_upcoming_deletion(
    msc: MediaServerClient,
    medias: list[dict],
    delete_date: date,
    skip_category: str,
    html_email_template: Path,
    plain_email_template: Path,
    email_subject_template: str,
    fallback_email: str,
    apply: bool = False,
):
    smtp_server = msc.conf.get('SMTP_SERVER')
    smtp_login = msc.conf.get('SMTP_LOGIN')
    smtp_password = msc.conf.get('SMTP_PASSWORD')
    smtp_email = msc.conf.get('SMTP_SENDER_EMAIL')
    if not (smtp_server and smtp_login and smtp_password and smtp_email):
        smtp_password = '*' * len(smtp_password)
        raise MisconfiguredError(f'{smtp_server=} / {smtp_login=} / {smtp_password=} / {smtp_email=}')
    html_template, plain_template = _get_templates(html_email_template, plain_email_template)

    users = _get_users(msc)
    valid_emails = {
        email: (user.get('speaker_id') or '').strip()
        for user in users
        if (email := (user.get('email') or '').strip()) and user['is_active']
    }
    emails_by_speaker_id = {v: k for k, v in valid_emails.items()}

    medias_per_speaker = {}
    to_fallback = []
    for media in medias:
        recipients = []
        speakers_ids = [
            speaker_id.strip()
            for speaker_id in (media.get('speaker_id') or '').split('|')
        ]
        speakers_emails = [
            speaker_email.strip()
            for speaker_email in (media.get('speaker_email') or '').split('|')
        ]
        for speaker_id, speaker_email in zip_longest(speakers_ids, speakers_emails):
            if not speaker_email and speaker_id:
                speaker_email = emails_by_speaker_id[speaker_id]
            if speaker_email and speaker_email in valid_emails:
                recipients.append(speaker_email)

        if not recipients:
            to_fallback.append(media)

        for speaker_email in recipients:
            medias_per_speaker.setdefault(speaker_email, []).append(media)

    to_send = {
        speaker_email: _prepare_mail(
            msc,
            sender=smtp_email,
            speaker_email=speaker_email,
            medias=speaker_medias,
            delete_date=delete_date,
            skip_category=skip_category,
            html_template=html_template,
            plain_template=plain_template,
            email_subject_template=email_subject_template,
        ) for speaker_email, speaker_medias in medias_per_speaker.items()
    }

    if apply:
        context = ssl.create_default_context()
        smtp_ctx_manager = smtplib.SMTP_SSL(smtp_server, 465, context=context)
    else:
        smtp_ctx_manager = nullcontext()

    sent_count = 0
    with smtp_ctx_manager as smtp:
        if apply:
            smtp.login(smtp_login, smtp_password)
        for recipient, (message, context) in to_send.items():
            try:
                if apply:
                    smtp.sendmail(smtp_email, recipient, message)
            except smtplib.SMTPException as err:
                logger.error(
                    f'Cannot send email to "{recipient}": {err}. '
                    'Medias will be added to the fallback recipient\'s email.'
                )
                to_fallback += medias_per_speaker[recipient]
            else:
                if apply:
                    logger.debug(f'Sent "{recipient}" an email about {context}.')
                else:
                    logger.debug(f'[Dry run] Would have sent "{recipient}" an email about {context}.')
                sent_count += 1
        if to_fallback:
            fallback_message, context = _prepare_mail(
                msc,
                sender=smtp_email,
                speaker_email=fallback_email,
                medias=to_fallback,
                delete_date=delete_date,
                skip_category=skip_category,
                html_template=html_template,
                plain_template=plain_template,
                email_subject_template=email_subject_template,
            )
            try:
                if apply:
                    smtp.sendmail(smtp_email, fallback_email, fallback_message)
            except Exception as err:
                logger.error(
                    f'Mail delivery to fallback email address "{fallback_email}" failed.\n'
                    f'{fallback_message}'
                )
                raise err
            else:
                if apply:
                    logger.debug(f'Sent "{fallback_email}" an email about {context}.')
                else:
                    logger.debug(f'[Dry run] Would have sent "{fallback_email}" an email about {context}.')
                sent_count += 1
        if apply:
            logger.info(f'Sent {sent_count} emails.')
        else:
            logger.info(f'[Dry run] {sent_count} emails would have been sent.')


def _delete_medias(msc: MediaServerClient, medias: list[dict], apply: bool = False):
    ms_url = msc.conf['SERVER_URL'] + '/permalink/'
    medias = {media['oid']: media for media in medias}
    deleted_count = 0
    deleted_size = 0
    if apply:
        response = msc.api(
            'catalog/bulk_delete/',
            method='post',
            data=dict(oids=list(medias.keys()))
        )
        for oid, result in response['statuses'].items():
            if result['status'] == 200:
                logger.debug(f'Media {ms_url}{oid} has been deleted.')
                deleted_count += 1
                deleted_size += medias[oid]['storage_used']
            else:
                err = result['message']
                logger.error(
                    f'An error occurred while attempting to delete media {ms_url}{oid}. '
                    f'The media has not been deleted: {err}.'
                )
        logger.info(
            f'{deleted_count} medias ({pp_size(deleted_size)}) have been successfully deleted.'
        )
    else:
        for oid, media in medias.items():
            logger.debug(f'[Dry run] Media {ms_url}{oid} would have been deleted.')
            deleted_count += 1
            deleted_size += media['storage_used']
        logger.info(
            f'[Dry run] {deleted_count} medias ({pp_size(deleted_size)}) would have been have been deleted.'
        )


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            '--conf',
            help='Path to the configuration file (e.g. myconfig.json).',
            required=True,
            type=str,
        )
        self.add_argument(
            '--delete-date',
            help='Date after which content will be deleted when running '
                 'the script, e.g. "2024-10-28"; running this script '
                 'before this date will result in notifying users, '
                 'otherwise it will delete the medias.',
            type=str,
            required=True,
        )
        self.add_argument(
            '--added-before',
            help='Maximum "add_date" for a media to be considered for '
                 'deletion (e.g. "2022-01-28"). Any media added on or '
                 'after this date will not be considered for deletion.',
            type=str,
            required=True,
        )
        self.add_argument(
            '--skip-category',
            help='Category name used to signify that content must be preserved.',
            type=str,
            default='do not delete',
        )
        self.add_argument(
            '--html-email-template',
            help='Path to HTML email template file. The template will be populated at '
                 'runtime with dynamic values via these 5 variables: platform_hostname, '
                 'media_count, delete_date, skip_category, list_of_media. Your template '
                 'should use Python new-style formatting syntax '
                 '(e.g.: "You have until {delete_date} to review each media").',
            type=Path,
            default='./email.html',
        )
        self.add_argument(
            '--plain-email-template',
            help='Path to plain email template file. This plain variant will be displayed '
                 'to users whose email client is set to prevent HTML in emails. The template '
                 'variables available are the same as for the "--html-email-template" argument.',
            type=Path,
            default='./email.txt',
        )
        self.add_argument(
            '--email-subject-template',
            help='Template string to use for the email subject line. The template '
                 'variables available are the same as for the "--html-email-template" argument.',
            type=str,
            default='Action required on the video platform {platform_hostname}: '
                    '{media_count} medias will be deleted on {delete_date}',
        )
        self.add_argument(
            '--fallback-email',
            help='Fallback recipient address. This address will receive a notification for all '
                 'medias that do not have speakers or for which none of the speakers point to '
                 'an existing user with a valid email address. Medias for which a notification '
                 'was sent but the delivery failed will also be added to the notification sent '
                 'to this address. If mail delivery to this fallback address fails, the script '
                 'will fail with an error. This ensures that at least one address is notified of '
                 'the impending deletion of any media.',
            type=str,
            required=True,
        )
        self.add_argument(
            '--apply',
            help='Whether to apply changes or not. '
                 'If not set, the script will simulate the work and generate logs. '
                 'It is a good idea to set "--log-level" to "debug" if "--apply" is not set.',
            action='store_true',
        )
        self.add_argument(
            '--test-email-template',
            help='Use this flag to test your email templates. '
                 'A single email will be printed to the console with dummy values. '
                 'No email will be sent and no media will be deleted.',
            action='store_true',
        )
        self.add_argument(
            '--log-level',
            help='Log level.',
            default='info',
            choices=['critical', 'error', 'warn', 'info', 'debug']
        )

    def error(self, message):
        self.print_help()
        sys.stderr.write('error: %s\n' % message)
        sys.exit(2)


def delete_old_medias(sys_args):
    parser = ArgumentParser(
        'mass_delete_old_medias',
        description=(
            'This script deletes (or warns speakers about the '
            'impending deletion of) medias added before a given date. '
            'To run this script properly, start by choosing a '
            '"--delete-date" in the future (you should give your users '
            'enough time to react to the deletion notifications). '
            'Then, choose a "--added-before" date that will be used to '
            'filter medias to consider for deletion. Fill out the '
            'other parameters to your liking then run the script. On '
            'the first run the script will warn every speaker of the '
            'impending deletion of their medias. You can run the '
            'script as many times as you want until the "--delete-date" '
            'to send reminders to speakers. Be sure to always use the '
            'same "--added-before" parameter as you did in the first '
            'run, to ensure, the medias considered for deletion are '
            'always the same. Finally, after the "--delete-date" has '
            'passed, run the script one more time, still with the same '
            '"--added-before" parameter as the first run. This last run '
            'will delete the medias to the recycle-bin (assuming the '
            'recycle-bin is activated, otherwise the deletion cannot be '
            'undone). You can repeat this whole process at regular '
            'intervals and with different parameters (every 6 months, '
            'every year...) to cleanup old medias.'
        )
    )
    args = parser.parse_args(sys_args)

    logging.basicConfig()
    logger.setLevel(args.log_level.upper())

    msc = MediaServerClient(args.conf)
    msc.conf['TIMEOUT'] = max(600, msc.conf['TIMEOUT'])

    if args.apply:
        answer = input(
            'The script is running in normal mode. '
            'Emails will be sent, medias will be deleted.\n'
            'Please ensure that the recycle-bin is enabled on your platform '
            f'{msc.conf["SERVER_URL"]}/admin/settings/#id_trash_enabled '
            'Proceed ? [y / n]'
        )
        if answer.lower() not in ['yes', 'y']:
            sys.exit(0)
    else:
        logger.info(
            '[Dry run] The script is running in dry-run mode. '
            'No email will be sent, no media will be deleted.'
        )
    today = date.today()
    delete_date = datetime.strptime(args.delete_date, "%Y-%m-%d").date()
    added_before_date = datetime.strptime(args.added_before, "%Y-%m-%d").date()
    skip_category = args.skip_category.strip()

    if args.test_email_template:
        html_template, plain_template = _get_templates(
            args.html_email_template,
            args.plain_email_template,
        )
        message, _context = _prepare_mail(
            msc,
            sender=msc.conf.get('SMTP_SENDER_EMAIL', 'your-smtp-account@example.com'),
            speaker_email=args.fallback_email,
            medias=DUMMY_MEDIAS,
            delete_date=delete_date,
            skip_category=skip_category,
            html_template=html_template,
            plain_template=plain_template,
            email_subject_template=args.email_subject_template,
        )
        logger.info(message)
    else:
        medias = _get_old_medias(msc, added_before_date, skip_category)
        if delete_date > today:
            _warn_speakers_about_upcoming_deletion(
                msc,
                medias,
                delete_date=delete_date,
                skip_category=skip_category,
                html_email_template=args.html_email_template,
                plain_email_template=args.plain_email_template,
                email_subject_template=args.email_subject_template,
                fallback_email=args.fallback_email,
                apply=args.apply,
            )
        else:
            _delete_medias(msc, medias, apply=args.apply)


if __name__ == '__main__':
    delete_old_medias(sys.argv[1:])
