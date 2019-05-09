from __future__ import absolute_import

import aiofiles

from instattack.exceptions import InvalidFileLine
from .logger import AppLogger


log = AppLogger(__file__)


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
