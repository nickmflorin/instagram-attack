import asyncio
import inspect
import re

from instattack import settings, logger
from instattack.src.utils import cancel_remaining_tasks, get_app_stack_at


"""
TODO:
----
We might want to set a max_tries parameter on the limit_on_success call
so we don't wind up making the same request hundreds of times if we run
into issues.
"""


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


async def limit_on_success(coros, batch_size, max_tries=None):
    """
    Runs single coroutine in batches until it returns a successful response or
    the number of attempts of the coroutine reaches the max limit.

    The batch number is maintained as tasks are finished and do not return
    the desired non-null result.
    """
    log = logger.get_async(__name__, subname='limit_on_success')

    futures = []
    while len(futures) < batch_size:
        try:
            c = await coros.__anext__()
        except StopAsyncIteration as e:
            break
        else:
            futures.append(asyncio.create_task(c))

    attempts = batch_size
    num_tries = 0

    while len(futures) > 0:
        await asyncio.sleep(0)  # Not sure why this is necessary but it is.
        for f in futures:
            if f.done():
                num_tries += 1
                if f.exception():
                    exc = f.exception()

                    stack = inspect.stack()
                    frame = get_app_stack_at(stack, step=1)

                    # The only benefit including the frame has is that the filename
                    # will not be in the logger, it will be in the last place before the
                    # logger and this statement.
                    # await log.traceback(exc.__class__, exc, exc.__traceback__,
                    #     extra={'frame': frame})
                    raise exc
                    # raise f.exception()
                else:
                    # If the future returned a result, schedule the remaining tasks
                    # to be cancelled and return the result.
                    if f.result():
                        asyncio.create_task(cancel_remaining_tasks(futures=futures))
                        return f.result(), num_tries
                    else:
                        futures.remove(f)
                        if not max_tries or attempts < max_tries:
                            try:
                                newc = await coros.__anext__()
                            except StopAsyncIteration as e:
                                pass
                            else:
                                futures.append(asyncio.create_task(newc))


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

    while len(futures) > 0:
        await asyncio.sleep(0)
        for f in futures:
            if f.done():
                if f.exception():
                    raise f.exception()
                else:
                    futures.remove(f)
                    try:
                        newc = await coros.__anext__()
                        futures.append(asyncio.create_task(newc))
                    except StopAsyncIteration as e:
                        pass
                    res = f.result()
                    if res.conclusive:
                        yield res
