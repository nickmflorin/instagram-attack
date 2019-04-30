from __future__ import absolute_import

from collections import Iterable

from .exceptions import InvalidFileLine, InvalidWriteElement


def ensure_iterable(arg):
    if isinstance(arg, str):
        return [arg]
    elif not isinstance(arg, Iterable):
        return [arg]
    return arg


def write_array_data(path, array):
    from instattack.logger import AppLogger
    log = AppLogger(__file__)

    lines = []
    for i, element in enumerate(array):
        element = "%s" % element
        if element.strip() == "" or element is None:
            exc = InvalidWriteElement(i, element)
            log.error(exc)
        else:
            lines.append(element)

    # TODO: Wrap around try/except maybe?
    data = "\n".join(lines)
    path.write(data, encoding='utf-8')


def read_raw_data(filepath, limit=None):
    from instattack.logger import AppLogger
    log = AppLogger(__file__)  # noqa

    raw_data = filepath.read()

    lines = []
    values = [val.strip() for val in raw_data.split('\n')]
    for i, val in enumerate(values):
        if val == "":
            exc = InvalidFileLine(i, val)  # noqa
            # Don't Log Empty Lines for Now
            # log.error(exc)
        else:
            lines.append(val)

    if limit:
        return lines[:limit]
    return lines
