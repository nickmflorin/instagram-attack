from __future__ import absolute_import

from instattack.lib.logger import AppLogger

from instattack.mgmt.exceptions import InvalidFileLine, InvalidWriteElement


log = AppLogger(__file__)


def write_array_data(path, array):

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
