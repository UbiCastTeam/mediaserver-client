from datetime import timedelta
import re
import sys


OBJECT_TYPES = {'v': 'video', 'l': 'live', 'p': 'photos', 'c': 'channel'}


# Terminal colors
if sys.stdout.isatty():
    class TTYColors:
        RED = '\033[31m'
        GREEN = '\033[32m'
        YELLOW = '\033[33m'
        BLUE = '\033[34m'
        PURPLE = '\033[35m'
        TEAL = '\033[36m'
        RESET = '\033[0m'
else:
    class TTYColors:
        RED = GREEN = YELLOW = BLUE = PURPLE = TEAL = RESET = ''


def _size_repr(value: int, unit: str, short: bool = True) -> str:
    # https://en.wikipedia.org/wiki/Template:Quantities_of_bytes
    if short:
        labels = {0: '', 1: 'k', 2: 'M', 3: 'G', 4: 'T', 5: 'P'}
    else:
        labels = {0: '', 1: 'kilo', 2: 'mega', 3: 'giga', 4: 'tera', 5: 'peta'}
    power = 1000
    n = 0
    while value > power and n < 5:
        value /= power
        n += 1
    return f'{round(value, 1)} {labels[n]}{unit}'


def format_bits(value: int, short: bool = True) -> str:
    unit = 'b' if short else 'bits'
    return _size_repr(value, unit, short=short)


def format_bytes(value: int, short: bool = True) -> str:
    unit = 'B' if short else 'bytes'
    return _size_repr(value, unit, short=short)


def format_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f'{h:d}:{m:02d}:{s:02d}'


def format_timedelta(delta: timedelta) -> str:
    if delta.days < 30:
        return f'{delta.days} days'

    years, days = divmod(delta.days, 365)
    months, days = divmod(days, 30)
    if years and months:
        return f'{years} years, {months} months'
    elif years:
        return f'{years} years'
    return f'{months} months'


def format_item(item: dict) -> str:
    txt = OBJECT_TYPES.get(item['oid'][0], item['oid'][0])
    txt += f' {item["oid"]}'
    if item.get('title'):
        title = item['title']
        if len(title) > 57:
            title = title[:57] + '...'
        txt += f' "{title}"'
    return txt


def format_item_file(item: dict) -> str:
    # This function does not handle all file systems, only most common ones (NTFS, ext4, HFS)
    # Characters limitation depending on file system:
    # https://en.wikipedia.org/wiki/Filename#Comparison_of_filename_limitations
    title = item.get('title')
    if item.get('title'):
        title = re.sub(r'["\'*/\\|:<>?]', ' ', item['title'])
        title = re.sub(r' +', ' ', title)
        title = title.strip(' -')
    if not title:
        title = 'channel' if item['oid'].startswith('c') else 'media'
    elif len(title) > 54:
        title = title[:54] + '...'
    return title + ' - ' + item['oid']
