import aiofiles


def read_raw_data(filepath, limit=None):
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
    from instattack.app.exceptions import InvalidFileLine

    count = 0

    lines = []
    with open(filepath) as f:
        for line in f.readlines():
            line = line.replace("\n", "")
            if line == "":
                exc = InvalidFileLine(i, val)  # noqa
                # log.error(exc) Don't Log Empty Lines for Now
            else:
                if not limit or count < limit:
                    lines.append(line)
                    count += 1
                else:
                    break
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
    from instattack.app.exceptions import InvalidFileLine

    count = 0
    async with aiofiles.open(filepath) as f:
        async for line in f:
            line = line.replace("\n", "")
            if line == "":
                exc = InvalidFileLine(i, val)  # noqa
                # log.error(exc) Don't Log Empty Lines for Now
            else:
                if not limit or count < limit:
                    yield line
                    count += 1
                else:
                    break
