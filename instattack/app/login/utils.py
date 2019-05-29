import asyncio
import re

from instattack import settings


async def get_token(session):
    """
    IMPORTANT:
    ---------
    The only reason to potentially use async retrieval of token would be if we
    wanted to use proxies and weren't sure how well the proxies would work.  It
    is much faster to just use a regular request, but does not protect identity.

    For now, we will go the faster route, but leave the code around that found
    the token through iterative async requests for the token.
    """
    async with session.get(settings.INSTAGRAM_URL) as response:
        text = await response.text()
        token = re.search('(?<="csrf_token":")\w+', text).group(0)
        return token, response.cookies


async def limit_as_completed(coros, batch_size):
    """
    Takes a generator yielding coroutines and runs the coroutines concurrently,
    similarly to asyncio.as_completed(tasks), except that it limits the number
    of concurrent tasks at any given time, specified by `batch_size`.

    When coroutines complete, and the pool of concurrent tasks drops below the
    batch_size, coroutines will be added to the batch until there are none left.and
    """
    futures = []
    while len(futures) < batch_size:
        try:
            c = await coros.__anext__()
        except StopAsyncIteration as e:
            break
        else:
            futures.append(asyncio.create_task(c))

    num_tries = 0

    while len(futures) > 0:
        await asyncio.sleep(0)  # Not sure why this is necessary but it is.
        for f in futures:
            if f.done():
                num_tries += 1
                if f.exception():
                    raise f.exception()
                else:
                    futures.remove(f)
                    try:
                        newc = await coros.__anext__()
                        futures.append(asyncio.create_task(newc))
                    except StopAsyncIteration as e:
                        pass
                    yield f.result(), num_tries
