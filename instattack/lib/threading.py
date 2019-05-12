import asyncio

from itertools import islice

from instattack.lib import AppLogger


log = AppLogger(__name__)


async def coro_exc_wrapper(coro, loop):
    try:
        await coro
    except Exception as e:
        loop.call_exception_handler({'message': str(e), 'exception': e})


async def first_successful_completion(coro, args, batch, limit):
    """
    Runs single coroutine in batches until it returns a successful response or
    the number of attempts of the coroutine reaches the max limit.

    The batch number is maintained as tasks are finished and do not return
    the desired non-null result.
    """
    futures = [
        asyncio.create_task(coro(*args))
        for i in range(batch)
    ]

    attempts = batch
    while len(futures) > 0:
        await asyncio.sleep(0)  # Not sure why this is necessary but it is.
        for f in futures:
            if f.done():
                if f.result():
                    asyncio.create_task(cancel_remaining_tasks(futures=futures))
                    return f.result()
                else:
                    if f.exception():
                        log.error(f.exception())
                    futures.remove(f)
                    if attempts < limit:
                        futures.append(asyncio.create_task(coro(*args)))


# Not currently being used but we want to hold onto.
def limited_as_completed(coros, limit):
    """
    Equivalent of asyncio.as_completed(tasks) except that it limits the number
    of concurrent tasks at any given time, and when that number falls below
    the limit it adds tasks back into the pool.
    """
    futures = [
        asyncio.ensure_future(c)
        for c in islice(coros, 0, limit)
    ]

    async def first_to_finish():
        while True:
            await asyncio.sleep(0)
            for f in futures:
                if f.done():
                    futures.remove(f)
                    try:
                        newf = next(coros)
                        futures.append(asyncio.ensure_future(newf))
                    except StopIteration as e:
                        pass
                    return f.result()
    while len(futures) > 0:
        yield first_to_finish()


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
