import asyncio

from instattack.utils import cancel_remaining_tasks
from instattack.logger import AppLogger


"""
TODO:
----
We might want to set a max_tries parameter on the limit_on_success call
so we don't wind up making the same request hundreds of times if we run
into issues.
"""


async def limit_on_success(coros, batch_size, max_tries=None):
    """
    Runs single coroutine in batches until it returns a successful response or
    the number of attempts of the coroutine reaches the max limit.

    The batch number is maintained as tasks are finished and do not return
    the desired non-null result.
    """
    log = AppLogger(f"{__name__}:limit_on_success")

    futures = []
    while len(futures) < batch_size:
        try:
            c = await coros.__anext__()
        except StopAsyncIteration as e:
            break
        else:
            futures.append(asyncio.create_task(c))

    attempts = batch_size
    while len(futures) > 0:
        await asyncio.sleep(0)  # Not sure why this is necessary but it is.
        for f in futures:
            if f.done():
                if f.exception():
                    raise f.exception()
                else:
                    # If the future returned a result, schedule the remaining tasks
                    # to be cancelled and return the result.
                    if f.result():
                        log.debug('Cancelling Remaining Generator Tasks')
                        asyncio.create_task(cancel_remaining_tasks(futures=futures))
                        return f.result()
                    else:
                        futures.remove(f)
                        if not max_tries or attempts < max_tries:
                            try:
                                newc = await coros.__anext__()
                            except StopAsyncIteration as e:
                                pass
                            else:
                                futures.append(asyncio.create_task(newc))


async def limit_as_completed(coros, batch_size, stop_on=None):
    """
    Takes a generator yielding coroutines and runs the coroutines concurrently,
    similarly to asyncio.as_completed(tasks), except that it limits the number
    of concurrent tasks at any given time, specified by `batch_size`.

    When coroutines complete, and the pool of concurrent tasks drops below the
    batch_size, coroutines will be added to the batch until there are none left.and
    """
    log = AppLogger(f"{__name__}:limit_as_completed")

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
                        log.debug('No More Coroutines in Generator')

                    res = f.result()
                    if stop_on:
                        if stop_on(res):
                            # We run into issues in the shutdown method when trying
                            # to cancel tasks if we don't await this.  This only happens
                            # for low numbers of passwords, since the tasks might not all
                            # be completed here by the time the shutdown() method is
                            # reached.
                            #   >> asyncio.create_task(cancel_remaining_tasks(futures))
                            log.debug('Cancelling Remaining Generator Tasks')
                            await cancel_remaining_tasks(futures=futures)
                    yield res
