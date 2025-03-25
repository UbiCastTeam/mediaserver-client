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
from datetime import date, datetime, timedelta
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
    '"{skip_categories}" category if you need to preserve this content. '
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
    '"{skip_categories}" category if you need to preserve this content. '
    'After this date, the media will be deleted. You can also delete '
    'it when you review it.</p>\n'
    '<p>List of media to review ({media_count}):</p>\n'
    '<ul>{list_of_media}</ul>\n'
)
DUMMY_MEDIAS = [
    {
        'oid': 'oid_1',
        'title': 'Media #1',
        'add_date': '2024-01-25 12:00:00',
        'storage_used': 10 * 1000 ** 3,  # 10 GB
        'views_last_year': 10,
        'views_last_month': 1,
    },
    {
        'oid': 'oid_2',
        'title': 'Media #2',
        'add_date': '2023-04-25 12:00:00',
        'storage_used': 20 * 1000 ** 3,  # 20 GB
        'views_last_year': 20,
        'views_last_month': 2,
    },
    {
        'oid': 'oid_3',
        'title': 'Media #3',
        'add_date': '2020-04-25 12:00:00',
        'storage_used': 30 * 1000 ** 3,  # 30 GB
        'views_last_year': 30,
        'views_last_month': 3,
    },
]


class MisconfiguredError(Exception):
    pass


def format_size(size_bytes: int) -> str:
    """
    Return human-readable size with automatic suffix.
    """
    for unit in ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z'):
        if abs(size_bytes) < 1000:
            return f'{size_bytes:.1f}{unit}B'
        size_bytes /= 1000
    return f'{size_bytes:.1f}YB'


def format_timedelta(delta: timedelta):
    if delta.days < 30:
        return f'{delta.days} days'

    years, days = divmod(delta.days, 365)
    months, days = divmod(days, 30)
    if years and months:
        return f'{years} years, {months} months'
    elif years:
        return f'{years} years'
    return f'{months} months'


def redact_password(password: str) -> str:
    return '*' * len(password) if password else ''


def _get_medias(
    msc: MediaServerClient,
    added_after: Optional[date] = None,
    added_before: Optional[date] = None,
    views_max_count: Optional[int] = None,
    views_playback_threshold: Optional[int] = None,
    views_after: Optional[date] = None,
    views_before: Optional[date] = None,
    skip_categories: list[str] = (),
) -> list[dict]:
    catalog = msc.get_catalog('flat')
    unwatched = {}
    if views_max_count is not None:
        unwatched = {
            unwatched['object_id']: unwatched['views_over_period']
            for unwatched in msc.api(
                'stats/unwatched/',
                params={
                    'playback_threshold': views_playback_threshold,
                    'views_threshold': views_max_count,
                    'recursive': 'yes',
                    'sd': views_after.strftime('%Y-%m-%d'),
                    'ed': views_before.strftime('%Y-%m-%d'),
                },
            )['unwatched']
        }

    channels = {channel['oid']: channel for channel in catalog['channels']}
    selected_medias = []
    for key in ('videos', 'lives'):
        medias = catalog.get(key, ())
        for media in medias:
            add_date = datetime.strptime(media['add_date'], '%Y-%m-%d %H:%M:%S').date()
            categories = {cat.strip(' \r\t').lower() for cat in (media['categories'] or '').strip('\n').split('\n')}
            media_pp = f'{media["title"]} [{media["oid"]}]'
            if added_before and add_date >= added_before:
                before_date_pp = added_before.strftime('%Y-%m-%d')
                logger.debug(
                    f'{media_pp} was skipped because it was added after {before_date_pp}.'
                )
            elif added_after and add_date < added_after:
                after_date_pp = added_after.strftime('%Y-%m-%d')
                logger.debug(
                    f'{media_pp} was skipped because it was added before {after_date_pp}.'
                )
            elif views_max_count and media['oid'] not in unwatched:
                views_after_pp = views_after.strftime('%Y-%m-%d')
                views_before_pp = views_before.strftime('%Y-%m-%d')
                logger.debug(
                    f'{media_pp} was skipped because it was viewed more than {views_max_count} '
                    f'times between {views_after_pp} and {views_before_pp}.'
                )
            elif skip_categories and (common_categories := categories.intersection(skip_categories)):
                logger.debug(
                    f'{media_pp} was skipped because it has the categories {common_categories}.'
                )
            else:
                if views_max_count:
                    media['views_over_period'] = unwatched[media['oid']]
                    media['views_after'] = views_after.strftime('%Y-%m-%d')
                    media['views_before'] = views_before.strftime('%Y-%m-%d')
                media['managers_emails'] = channels.get(media['parent_oid'], {}).get('managers_emails')
                selected_medias.append(media)

    storage_used = sum(media['storage_used'] for media in selected_medias)
    logger.info(
        f'Found {len(selected_medias)} medias matching the given filters '
        f'(size: {format_size(storage_used)}).'
    )
    return selected_medias


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
    skip_categories: list[str],
    html_template: Optional[str],
    plain_template: Optional[str],
    email_subject_template: str,
) -> tuple[str, dict]:
    # Ensure each media is only once in the list.
    medias = list({media['oid']: media for media in medias}.values())

    ms_perma_url = msc.conf['SERVER_URL'] + '/permalink/'
    ms_edit_url = msc.conf['SERVER_URL'] + '/edit/iframe/'
    context = {
        'media_count': len(medias),
        'media_size_pp': format_size(sum(media['storage_used'] for media in medias)),
        'delete_date': delete_date.strftime('%B %d, %Y'),
        'skip_categories': ' | '.join(f'"{cat}"' for cat in skip_categories),
        'platform_hostname': urlparse(msc.conf['SERVER_URL']).netloc,
    }
    message = MIMEMultipart('alternative')
    message['Subject'] = email_subject_template.format(**context)
    message['From'] = sender
    message['To'] = speaker_email

    media_contexts = []
    now = datetime.now()
    for media in medias:
        media_add_date = datetime.strptime(media['add_date'], '%Y-%m-%d %H:%M:%S')
        media_context = {
            'title': media['title'],
            'add_date': media_add_date.strftime('%Y-%m-%d'),
            'age': format_timedelta(now - media_add_date),
            'view_url': f'{ms_perma_url}{media["oid"]}/iframe/',
            'edit_url': f'{ms_edit_url}{media["oid"]}/#id_categories',
        }
        if 'views_over_period' in media:
            media_context['views'] = (
                f'{media["views_over_period"]} times between '
                f'{media["views_after"]} and {media["views_before"]}'
            )
        else:
            media_context['views'] = (
                f'{media["views_last_year"]} times last year, '
                f'{media["views_last_month"]} times last month'
            )
        media_contexts.append(media_context)
    if plain_template:
        plain_media_list = '\n'.join(
            (
                '\t- {view_url} - "{title}" - added on {add_date} ({age} ago), viewed {views} '
                '(click here {edit_url} to protect against deletion)'
            ).format(**ctx)
            for ctx in media_contexts
        )
        plain = plain_template.format(list_of_media=plain_media_list, **context)
        message.attach(MIMEText(plain, 'plain'))
    if html_template:
        html_media_list = '\n'.join(
            (
                '<li><a href="{view_url}">"{title}"</a> added on {add_date} ({age} ago), viewed {views} '
                '(click <a href="{edit_url}">here</a> to protect against deletion)</li>'
            ).format(**ctx)
            for ctx in media_contexts
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


def _warn_speakers_about_deletion(
    msc: MediaServerClient,
    medias: list[dict],
    delete_date: date,
    skip_categories: list[str],
    html_email_template: Path,
    plain_email_template: Path,
    email_subject_template: str,
    fallback_to_channel_manager: bool,
    fallback_email: str,
    apply: bool = False,
):
    smtp_server = msc.conf.get('SMTP_SERVER')
    smtp_port = msc.conf.get('SMTP_PORT', 587)
    smtp_login = msc.conf.get('SMTP_LOGIN')
    smtp_password = msc.conf.get('SMTP_PASSWORD')
    smtp_email = msc.conf.get('SMTP_SENDER_EMAIL')
    if not (smtp_server and smtp_login and smtp_password and smtp_email):
        smtp_password = redact_password(smtp_password)
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
            if speaker_email and speaker_email in valid_emails:
                recipients.append(speaker_email)
            elif speaker_id and emails_by_speaker_id[speaker_id] in valid_emails:
                recipients.append(emails_by_speaker_id[speaker_id])
            elif fallback_to_channel_manager and media['managers_emails']:
                for manager_email in media['managers_emails'].split('\n'):
                    manager_email = manager_email.strip(' \r\t').lower()
                    if not manager_email.startswith('#') and manager_email in valid_emails:
                        recipients.append(manager_email)

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
            skip_categories=skip_categories,
            html_template=html_template,
            plain_template=plain_template,
            email_subject_template=email_subject_template,
        ) for speaker_email, speaker_medias in medias_per_speaker.items()
    }

    if apply:
        context = ssl.create_default_context()
        smtp_ctx_manager = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
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
                skip_categories=skip_categories,
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
    if not medias:
        logger.info('No media to delete.')
        return
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
            f'{deleted_count} medias ({format_size(deleted_size)}) have been successfully deleted.'
        )
    else:
        for oid, media in medias.items():
            logger.debug(f'[Dry run] Media {ms_url}{oid} would have been deleted.')
            deleted_count += 1
            deleted_size += media['storage_used']
        logger.info(
            f'[Dry run] {deleted_count} medias ({format_size(deleted_size)}) '
            f'would have been have been deleted.'
        )


def delete_old_medias(sys_args):
    parser = argparse.ArgumentParser(
        'mass_delete_old_medias',
        description=(
            'This script deletes (or warns speakers about the impending deletion of) medias '
            'matching certain filters. To run this script properly, start by choosing a '
            '"--delete-date" set in the future (you should give your users enough time to react '
            'to the deletion notifications). Then, choose at least one filter among:'
            '\n\t- "--added-after" date, to select only media that were added after the given '
            'date.'
            '\n\t- "--added-before" date, to select only media that were added before the given '
            'date.'
            '\n\t- "–-views-max-count", to select only medias that have had less than the given '
            'number of views over a given period ("--views-after" / "--views-before"). When '
            'this parameter is given, an additional parameter ("--views-playback-threshold") can '
            'be used to count only views where the playback time is above a number of seconds.'
            '\nWhen applying multiple filters, only medias that match all the filters are '
            'considered for deletion. If no filters are given, to prevent mistakes, the command '
            'will error out without doing anything.'
            '\n\nFill out the other parameters to your liking then run the script. On the first '
            'run, the script will warn every speaker of the impending deletion of their medias. '
            'You can run the script as many times as you want until the "--delete-date" to send '
            'reminders to speakers. Be sure to always use the same filters as you did during the '
            'first run, to ensure, the medias considered for deletion are always the same. '
            'Finally, after the "--delete-date" has passed, run the script one more time, still '
            'with the same filters as the first run. This last run will delete the medias to the '
            'recycle-bin (assuming the recycle-bin is activated, otherwise the deletion cannot be '
            'undone). You can repeat this whole process at regular intervals and with different '
            'parameters (every 6 months, every year...) to cleanup old medias.'
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--conf',
        help='Path to the configuration file (e.g. myconfig.json).',
        required=True,
        type=str,
    )
    parser.add_argument(
        '--delete-date',
        help='Date after which content will be deleted when running the script, e.g. "2024-10-28"; '
             'running this script before this date will result in notifying users, otherwise it '
             'will delete the medias.',
        type=str,
        required=True,
    )
    parser.add_argument(
        '--added-after',
        help='Minimum "add_date" for a media to be considered for deletion (e.g. "2022-01-28"). '
             'Any media added before this date will not be considered for deletion.',
        type=str,
        required=False,
    )
    parser.add_argument(
        '--added-before',
        help='Maximum "add_date" for a media to be considered for deletion (e.g. "2022-01-28"). '
             'Any media added on or after this date will not be considered for deletion.',
        type=str,
        required=False,
    )
    parser.add_argument(
        '--views-max-count',
        help='Maximum number of views a media can have over a given period ("--views-after" '
             '/ "--views-before") to be considered for deletion (e.g.: --views-max-count=3 to '
             'select only media that have 3 views or less during the given period). Any media '
             'that has been viewed more times than this number over the given period will not be '
             'considered for deletion. If this parameter is given, then both "--views-after" '
             'and "--views-before" must be given too (and they must be in the past). The script '
             'will error out before doing anything if that is not the case. This ensures the '
             'selection remains the same between runs.',
        type=int,
        required=False,
    )
    parser.add_argument(
        '--views-playback-threshold',
        help='Minimum time played (in seconds) to count as a view. Defaults to 0 (meaning any view '
             'with a duration above 0 is counted). If "–-views-max-count" is not given, this '
             'parameter will be ignored. Example: --views-max-count=3 --views-playback-threshold=5 '
             'will select only media that have been viewed 3 times or less for more than 5 seconds.',
        type=int,
        required=False,
        default=0,
    )
    parser.add_argument(
        '--views-after',
        help='Start of the period to consider for the "–-views-max-count" parameter. If '
             '"–-views-max-count" is not given, this parameter will be ignored. Required '
             'if "--views-max-count" is given. Examples: "2020-09-01".',
        type=str,
        required=False,
    )
    parser.add_argument(
        '--views-before',
        help='End of the period to consider for the "–-views-max-count" parameter. If '
             '"–-views-max-count" is not given, this parameter will be ignored. Required '
             'if "--views-max-count" is given. Examples: "2021-08-31".',
        type=str,
        required=False,
    )
    parser.add_argument(
        '--skip-category',
        help='Category name used to signify that content must be preserved. Can be '
             'passed multiple times to skip multiple categories '
             '(e.g.: --skip-category="do not delete" --skip-category="to keep"). '
             'Default is --skip-category="do not delete"',
        dest='skip_categories',
        action='append',
        default=[],
    )
    parser.add_argument(
        '--html-email-template',
        help='Path to HTML email template file. The template will be populated at runtime with '
             'dynamic values via these 5 variables: platform_hostname, media_count, delete_date, '
             'skip_categories, list_of_media. Your template should use Python new-style formatting '
             'syntax (e.g.: "You have until {delete_date} to review each media").',
        type=Path,
        default='./email.html',
    )
    parser.add_argument(
        '--plain-email-template',
        help='Path to plain email template file. This plain variant will be displayed to users '
             'whose email client is set to prevent HTML in emails. The template variables '
             'available are the same as for the "--html-email-template" argument.',
        type=Path,
        default='./email.txt',
    )
    parser.add_argument(
        '--email-subject-template',
        help='Template string to use for the email subject line. The template variables available '
             'are the same as for the "--html-email-template" argument.',
        type=str,
        default='Action required on the video platform {platform_hostname}: '
                '{media_count} medias will be deleted on {delete_date}',
    )
    parser.add_argument(
        '--send-email-on-deletion',
        help='Notify users on deletion of the list of deleted media and the freed storage summary. '
             'Use "--html-email-template", "--plain-email-template" and "--email-subject-template" '
             'to customize the emails sent on deletion.',
        action='store_true',
        required=False,
        default=False,
    )
    parser.add_argument(
        '--fallback-to-channel-manager',
        help='If medias do not have speakers or if none of the speakers point to an existing '
             'user, send an email to the channel manager if one exists (it must point to an '
             'existing user in the database too).',
        action='store_true',
        required=False,
        default=False,
    )
    parser.add_argument(
        '--fallback-email',
        help='Fallback recipient address. This address will receive a notification for all medias '
             'that do not have speakers/channel-managers or for which none of the speakers/'
             'channel-managers point to an existing user with a valid email address. Medias for '
             'which a notification was sent but the delivery failed will also be added to the '
             'notification sent to this address. If mail delivery to this fallback address fails, '
             'the script will fail with an error. This ensures that at least one address is '
             'notified of the impending deletion of any media.',
        type=str,
        required=True,
    )
    parser.add_argument(
        '--apply',
        help='Whether to apply changes or not. If not set, the script will simulate the work and '
             'generate logs. It is a good idea to set "--log-level" to "debug" if "--apply" is '
             'not set.',
        action='store_true',
    )
    parser.add_argument(
        '--test-email-template',
        help='Use this flag to test your email templates. A single email will be printed to the '
             'console with dummy values. No email will be sent and no media will be deleted.',
        action='store_true',
    )
    parser.add_argument(
        '--send-test-email-to',
        help='Use this flag to define an email address to send your template test to '
             '(use with conjunction with --test-email-template.'
    )
    parser.add_argument(
        '--log-level',
        help='Log level.',
        default='info',
        choices=['critical', 'error', 'warn', 'info', 'debug']
    )
    args = parser.parse_args(sys_args)

    logger.addHandler(logging.StreamHandler())
    logging.basicConfig(filename=f'mass-delete-old-medias-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log')
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
    delete_date = datetime.strptime(args.delete_date, '%Y-%m-%d').date()
    added_after = None
    added_before = None
    views_max_count = args.views_max_count
    views_playback_threshold = args.views_playback_threshold
    views_after = None
    views_before = None
    if args.added_after:
        added_after = datetime.strptime(args.added_after, '%Y-%m-%d').date()
    if args.added_before:
        added_before = datetime.strptime(args.added_before, '%Y-%m-%d').date()
    if args.views_after:
        views_after = datetime.strptime(args.views_after, '%Y-%m-%d').date()
    if args.views_before:
        views_before = datetime.strptime(args.views_before, '%Y-%m-%d').date()

    if not any((views_max_count, added_after, added_before)):
        raise MisconfiguredError(
            'At least one filter ("--added-after", "--added-before", '
            '"--views-max-count") is required.'
        )
    safe_end_date = today - timedelta(days=1)
    if views_max_count is None:
        views_playback_threshold = None
        views_after = None
        views_before = None
    elif views_max_count < 0:
        raise MisconfiguredError('If given, "--views-max-count" must be >= 0.')
    elif (
        not views_after or views_after > safe_end_date
        or not views_before or views_before > safe_end_date
    ):
        raise MisconfiguredError(
            'Both "--views-after" or "--views-before" must be given with "--views-max-count" '
            'to prevent deleting newer videos for which stats may not have been computed yet.'
            f'It must be at most {safe_end_date.strftime("%Y-%m-%d")}'
        )

    skip_categories = args.skip_categories or ['do not delete']

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
            skip_categories=skip_categories,
            html_template=html_template,
            plain_template=plain_template,
            email_subject_template=args.email_subject_template,
        )
        logger.info(message)
        if recipient := args.send_test_email_to:
            smtp_server = msc.conf.get('SMTP_SERVER')
            smtp_port = msc.conf.get('SMTP_PORT', 587)
            smtp_login = msc.conf.get('SMTP_LOGIN')
            smtp_password = msc.conf.get('SMTP_PASSWORD')
            smtp_email = msc.conf.get('SMTP_SENDER_EMAIL')
            if not (smtp_server and smtp_login and smtp_password and smtp_email):
                smtp_password = redact_password(smtp_password)
                raise MisconfiguredError(f'{smtp_server=} / {smtp_login=} / {smtp_password=} / {smtp_email=}')

            logger.info(f"Trying to send test email to {recipient} via {smtp_login}:{redact_password(smtp_password)}@{smtp_server}:{smtp_port}")

            context = ssl.create_default_context()
            smtp_ctx_manager = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=10)

            with smtp_ctx_manager as smtp:
                smtp.login(smtp_login, smtp_password)
                try:
                    smtp.sendmail(smtp_email, recipient, message)
                except smtplib.SMTPException as err:
                    logger.error(
                        f'Cannot send email to "{recipient}": {err}. '
                        'Medias will be added to the fallback recipient\'s email.'
                    )
    else:
        medias = _get_medias(
            msc,
            added_after=added_after,
            added_before=added_before,
            views_max_count=views_max_count,
            views_playback_threshold=views_playback_threshold,
            views_after=views_after,
            views_before=views_before,
            skip_categories=skip_categories,
        )
        if delete_date > today or args.send_email_on_deletion:
            _warn_speakers_about_deletion(
                msc,
                medias,
                delete_date=delete_date,
                skip_categories=skip_categories,
                html_email_template=args.html_email_template,
                plain_email_template=args.plain_email_template,
                email_subject_template=args.email_subject_template,
                fallback_to_channel_manager=args.fallback_to_channel_manager,
                fallback_email=args.fallback_email,
                apply=args.apply,
            )
        if delete_date <= today:
            _delete_medias(msc, medias, apply=args.apply)


if __name__ == '__main__':
    delete_old_medias(sys.argv[1:])
