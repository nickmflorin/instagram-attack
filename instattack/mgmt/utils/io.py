from __future__ import absolute_import

import aiofiles

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


async def stream_raw_data(filepath, limit=None):
    """
    Code Snippet
    ------------
    http://blog.mathieu-leplatre.info/some-python-3-asyncio-snippets.html

    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF.
            break
        yield line
    """
    count = 0
    async with aiofiles.open(filepath) as f:
        async for line in f:
            if line == "":
                exc = InvalidFileLine(i, val)  # noqa
                # log.error(exc) Don't Log Empty Lines for Now
            else:
                if limit and count == limit - 1:
                    break
                yield line
