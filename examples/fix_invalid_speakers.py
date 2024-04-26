#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field, fields
from datetime import date
from itertools import zip_longest
import logging
import os
from pathlib import Path
import sys
from typing import NamedTuple, Optional
import urllib.parse

try:
    from ms_client.client import MediaServerClient
except ModuleNotFoundError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ms_client.client import MediaServerClient


logger = logging.getLogger(__name__)


class Speaker(NamedTuple):
    email: Optional[str]
    id: Optional[str]
    name: Optional[str]


@dataclass
class CSVSpeakerData:
    email: str
    ids: set[str] = field(default_factory=set)
    names: set[str] = field(default_factory=set)
    url: Optional[str] = None
    reasons: set[str] = field(default_factory=set)
    corrected_email: Optional[str] = None
    corrected_id: Optional[str] = None
    corrected_name: Optional[str] = None

    @classmethod
    def get_csv_header(cls) -> list[str]:
        return [f.name for f in fields(cls)]

    @classmethod
    def from_csv_row(cls, csv_row: dict[str, Optional[str]]) -> CSVSpeakerData:
        return cls(
            email=csv_row['email'].strip(),
            ids=set(
                clean_spk_id
                for spk_id in csv_row['ids'].split(',')
                if (clean_spk_id := spk_id.strip())
            ),
            names=set(
                clean_name
                for name in csv_row['names'].split(',')
                if (clean_name := name.strip())
            ),
            url=csv_row['url'].strip(),
            reasons=set(
                clean_reason
                for reason in csv_row['reasons'].split(',')
                if (clean_reason := reason.strip())
            ),
            corrected_email=csv_row['corrected_email'].strip(),
            corrected_id=csv_row['corrected_id'].strip(),
            corrected_name=csv_row['corrected_name'].strip(),
        )

    def to_csv_row(self) -> dict[str, Optional[str]]:
        return {
            'email': self.email,
            'ids': ', '.join(sorted(self.ids)),
            'names': ', '.join(sorted(self.names)),
            'url': self.url,
            'reasons': ', '.join(sorted(self.reasons)),
            'corrected_email': self.corrected_email,
            'corrected_id': self.corrected_id,
            'corrected_name': self.corrected_name,
        }


def _get_speakers_by_oid(msc: MediaServerClient) -> dict[str, list[Speaker]]:
    speakers = {}
    catalog = msc.get_catalog(fmt='flat')
    for key in ['channels', 'videos', 'lives', 'photos']:
        for obj in catalog.get(key, []):
            oid = obj['oid']
            if key == 'channels':
                obj = obj.get('default_settings')
                if not obj:
                    continue
            speakers_ids, speakers_emails, speakers_names = [], [], []
            if obj.get('speaker_id'):
                speakers_ids = [
                    speaker_id.strip()
                    for speaker_id in obj.get('speaker_id').split('|')
                ]
            if obj.get('speaker_email'):
                speakers_emails = [
                    speaker_email.strip()
                    for speaker_email in obj.get('speaker_email').split('|')
                ]
            if obj.get('speaker'):
                speakers_names = [
                    speaker_name.strip()
                    for speaker_name in obj.get('speaker').split('|')
                ]
            if len({
                len(lst)
                for lst in [speakers_emails, speakers_ids, speakers_names]
                if lst
            }) > 1:
                logger.error(
                    f'Media "{oid}" will be ignored because its speakers '
                    f'cannot be parsed reliably: {[speakers_emails, speakers_ids, speakers_names]}'
                )
                continue
            speakers[oid] = [
                Speaker(speaker_email, speaker_id, speaker_name)
                for speaker_email, speaker_id, speaker_name in zip_longest(
                    speakers_emails, speakers_ids, speakers_names
                )
            ]
    return speakers


def _get_users(msc: MediaServerClient, page_size=500):
    users = []
    offset = 0
    response = msc.api('users/', params={'limit': page_size, 'offset': offset})
    while response['users']:
        users += response['users']
        offset += page_size
        if len(response['users']) < page_size:
            break
        response = msc.api('users/', params={'limit': page_size, 'offset': offset})
    return users


def _list_invalid_speakers(
    msc: MediaServerClient,
    csv_file: Path,
    name_format: str,
    ignore_errors: list[str],
):
    speakers_by_oid = _get_speakers_by_oid(msc)
    valid_emails = {
        email: user
        for user in _get_users(msc)
        if (email := (user.get('email') or '').strip())
    }

    speaker_data_by_email: dict[str, CSVSpeakerData] = {}
    for oid, speakers in speakers_by_oid.items():
        for speaker in speakers:
            if speaker.email:
                data = speaker_data_by_email.setdefault(
                    speaker.email,
                    CSVSpeakerData(speaker.email)
                )
                if speaker.id:
                    data.ids.add(speaker.id)
                if speaker.name:
                    data.names.add(speaker.name)
                data.url = (
                    f'{msc.conf["SERVER_URL"]}/search/'
                    f'?text={urllib.parse.quote_plus(speaker.email)}'
                    f'&in_speaker&for_videos&for_lives&for_photos'
                )

    with csv_file.open('w', newline='') as csvfile:
        speakers_writer = csv.DictWriter(
            csvfile,
            fieldnames=CSVSpeakerData.get_csv_header(),
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL
        )
        speakers_writer.writeheader()
        for speaker_data in speaker_data_by_email.values():
            if speaker_data.email in valid_emails:
                user = valid_emails[speaker_data.email]
                user_speaker_id = (user.get('speaker_id') or '').strip()
                user_first_name = (user.get('first_name') or '').strip()
                user_last_name = (user.get('last_name') or '').strip()
                if user_first_name or user_last_name:
                    user_fullname = name_format.format(
                        first_name=user_first_name, last_name=user_last_name
                    ).strip()
                else:
                    user_fullname = speaker_data.email.rsplit('@', 1)[0]

                if user_speaker_id and speaker_data.ids and not any(
                    spk_id == user_speaker_id
                    for spk_id in speaker_data.ids
                ):
                    speaker_data.reasons.add('INVALID_ID')
                if user_fullname and speaker_data.names and not any(
                    name == user_fullname
                    for name in speaker_data.names
                ):
                    speaker_data.reasons.add('INVALID_NAME')
            else:
                speaker_data.reasons.add('INVALID_EMAIL')
            if len(speaker_data.ids) > 1:
                speaker_data.reasons.add('MULTIPLE_ID')
            if len(speaker_data.names) > 1:
                speaker_data.reasons.add('MULTIPLE_NAME')
            speaker_data.reasons.difference_update(ignore_errors)
            if speaker_data.reasons:
                speakers_writer.writerow(speaker_data.to_csv_row())


def _fix_invalid_speakers(
    msc: MediaServerClient,
    csv_file: Path,
    apply: bool = False
):
    with csv_file.open('r', newline='') as csvfile:
        speakers_reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
        corrections: dict[str, CSVSpeakerData] = {}
        for row in speakers_reader:
            correction = CSVSpeakerData.from_csv_row(row)
            corrections[correction.email] = correction

    speakers_by_oid = _get_speakers_by_oid(msc)
    corrected_speakers_by_oid = {}
    for oid, current_speakers in speakers_by_oid.items():
        corrected_speakers = []
        for speaker in current_speakers:
            if speaker.email not in corrections:
                logger.debug(f'"{speaker.email}" not in CSV. Skipping...')
                corrected_speakers.append(speaker)
                continue
            correction = corrections[speaker.email]
            if (
                not correction.corrected_email
                and not correction.corrected_id
                and not correction.corrected_name
            ):
                logger.debug(f'No corrections for "{speaker.email}". Skipping...')
                corrected_speakers.append(speaker)
                continue

            corrected_email = speaker.email
            if correction.corrected_email == 'DELETE':
                corrected_email = ''
            elif correction.corrected_email:
                corrected_email = correction.corrected_email
            corrected_id = speaker.id
            if correction.corrected_id == 'DELETE':
                corrected_id = ''
            elif correction.corrected_id:
                corrected_id = correction.corrected_id
            corrected_name = speaker.name
            if correction.corrected_name == 'DELETE':
                corrected_name = ''
            elif correction.corrected_name:
                corrected_name = correction.corrected_name
            if any((corrected_email, corrected_id, corrected_name)):
                corrected_speakers.append(
                    Speaker(corrected_email, corrected_id, corrected_name)
                )
        if current_speakers != corrected_speakers:
            # Integrity check
            emails = [spk.email for spk in corrected_speakers if spk.email]
            ids = [spk.id for spk in corrected_speakers if spk.id]
            if len(emails) > len(set(emails)) or len(ids) > len(set(ids)):
                logger.error(
                    'Your corrections would lead to a speaker duplicate '
                    f'on media "{oid}": {current_speakers=} / {corrected_speakers=}. '
                    'This media will not be updated automatically by this script. '
                    'You might need to surgically edit this media by hand or fix your CSV file. '
                    'Alternatively, you might need to let the script run once to fix all other '
                    'medias and treat these errors in a separate run.'
                )
            else:
                corrected_speakers_by_oid[oid] = corrected_speakers

    for oid, corrected_speakers in corrected_speakers_by_oid.items():
        payload = {
            'speaker_email': '|'.join(spk.email for spk in corrected_speakers),
            'speaker_id': '|'.join(spk.id for spk in corrected_speakers),
            'speaker': '|'.join(spk.name for spk in corrected_speakers),
        }
        if apply:
            if oid[0] == 'c':
                payload['channel_oid'] = oid
                url = 'settings/defaults/metadata/edit/'
            else:
                payload['oid'] = oid
                url = 'medias/edit/'
            msc.api(url, method='post', data=payload)
            logger.info(
                f'Media "{oid}" has been updated: '
                f'old_speakers={speakers_by_oid[oid]}, new_speakers={corrected_speakers}'
            )
        else:
            logger.info(
                f'[Dry-run] Media "{oid}" would have been updated: '
                f'old_speakers={speakers_by_oid[oid]}, new_speakers={corrected_speakers}'
            )


def fix_invalid_speakers(sys_args):
    parser = argparse.ArgumentParser(
        'fix_invalid_speakers',
        description=(
            'This script has 2 modes: "list" mode and "fix" mode. You should run the '
            'script in "list" mode first. This will output a CSV file of invalid speakers.\n'
            '- the first column is the speaker email.\n'
            '- the second column is the associated speaker_id(s).\n'
            '- the third column is the associated speaker_name(s).\n'
            '- the fourth column is a link to a Nudgis search page for this specific speaker '
            'email (works best if you disable approximate search).\n'
            '- the fifth column is the reason(s) why this speaker was flagged as invalid. This '
            'column can list up to 5 reasons:\n'
            '\t* INVALID_EMAIL: the speaker email cannot be found in the user database. This can '
            'be the result of a user changing their email address or a former user account being '
            'deleted.\n'
            '\t* INVALID_ID: the speaker email belongs to a user that has a different speaker_id.\n'
            '\t* MULTIPLE_ID: the speaker email is associated with multiple user ids. This is '
            'usually the result of miss-typed input data.\n'
            '\t* INVALID_NAME: the speaker email belongs to a user that has a different name.\n'
            '\t* MULTIPLE_NAME: the speaker email is associated with multiple user names. This is '
            'usually the result of miss-typed input data.\n'
            '- the sixth column is left empty. You should fill this column with the corrected '
            'email address for this speaker. Leave this column empty if the email address does '
            'not need to be modified. Use the special token "DELETE" to blank the email address '
            'for this speaker (warning: this will affect as many medias as this speaker email is '
            'associated with).\n'
            '- the seventh column is left empty. You should fill this column with the corrected '
            'speaker id for this speaker. Leave this column empty if the speaker id does not need '
            'to be modified. Use the special token "DELETE" to blank the speaker id for this '
            'speaker (warning: this will affect as many medias as this speaker email is '
            'associated with).\n'
            '- the eights column is left empty. You should fill this column with the corrected '
            'name for this speaker. Leave this column empty if the name does not need to be '
            'modified. Use the special token "DELETE" to blank the name for this speaker '
            '(warning: this will affect as many medias as this speaker email is associated with).\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--conf',
        help='Path to the configuration file (e.g. myconfig.json).',
        required=True,
        type=str,
    )
    parser.add_argument(
        '--action',
        help='Action that the script should take. In list mode, the script will '
             'output a CSV file of the invalid speakers in `--csv-file`. In fix mode, '
             'the script will read the csv file from `--csv-file` and apply the fixes '
             'to the mediaserver database.',
        default='list',
        choices=['list', 'fix']
    )
    parser.add_argument(
        '--csv-file',
        help='Path where the CSV file will be read from / writen to. The CSV file '
             'uses commas (",") as a delimiter and pipes ("|") as quote characters.',
        default=f'./invalid_speakers_{date.today().strftime("%Y-%m-%d")}.csv',
        type=Path,
    )
    parser.add_argument(
        '--name-format',
        help='Format of a valid user\'s full name (for the reported errors). By default, '
             'the script uses --name-format="{first_name} {last_name}", which will consider '
             '"John Doe" valid, but not "Doe, John". For "Doe, John" to be  considered '
             'valid, you would need to pass --name-format="{last_name}, {first_name}".',
        default='{first_name} {last_name}',
        type=str,
    )
    parser.add_argument(
        '--ignore-errors',
        help='By default the script reports all errors. You can pass the error types to '
             'be ignored using this argument. To ignore multiple error types, pass this '
             'argument multiple times '
             '(e.g.: --ignore-errors=INVALID_NAME --ignore-errors=MULTIPLE_NAME).',
        action='append',
        default=[],
    )
    parser.add_argument(
        '--apply',
        help='Whether to apply changes or not. If not set, the script will simulate '
             'the work and generate logs. It is a good idea to set "--log-level" to '
             '"debug" if "--apply" is not set. This parameter only has effect in '
             '"fix" mode (because "list" mode does not make any changes by design).',
        action='store_true',
    )
    parser.add_argument(
        '--log-level',
        help='Log level.',
        default='info',
        choices=['critical', 'error', 'warn', 'info', 'debug']
    )
    args = parser.parse_args(sys_args)

    logging.basicConfig()
    logger.setLevel(args.log_level.upper())

    msc = MediaServerClient(args.conf)
    msc.conf['TIMEOUT'] = max(600, msc.conf['TIMEOUT'])

    if args.action == 'list':
        _list_invalid_speakers(msc, args.csv_file, args.name_format, args.ignore_errors)
    elif args.action == 'fix':
        if args.apply:
            answer = input(
                'The script is running in normal mode. Changes from '
                f'"{args.csv_file}" will be applied to the {msc.conf["SERVER_URL"]} database.\n'
                'Proceed ? [y / n]'
            )
            if answer.lower() not in ['yes', 'y']:
                sys.exit(0)
        else:
            logger.info(
                '[Dry run] The script is running in dry-run mode. '
                'No changes will be applied.'
            )
        _fix_invalid_speakers(msc, args.csv_file, args.apply)


if __name__ == '__main__':
    fix_invalid_speakers(sys.argv[1:])
