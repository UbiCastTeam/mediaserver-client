
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


def bits_repr(value: int, short: bool = True) -> str:
    unit = 'b' if short else 'bits'
    return _size_repr(value, unit, short=short)


def bytes_repr(value: int, short: bool = True) -> str:
    unit = 'B' if short else 'bytes'
    return _size_repr(value, unit, short=short)


def time_repr(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f'{h:d}:{m:02d}:{s:02d}'


def item_repr(item: dict) -> str:
    txt = item['oid']
    if item.get('title'):
        txt += ' ' + item['title']
    return txt
