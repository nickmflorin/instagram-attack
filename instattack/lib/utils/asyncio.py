import asyncio
import inspect

from instattack.lib import logger

from .paths import task_is_third_party


async def ensure_async_generator(iterable):
    if inspect.isasyncgen(iterable):
        async for proxy in iterable:
            yield proxy
    else:
        for proxy in iterable:
            yield proxy


async def coro_exc_wrapper(coro, loop):
    try:
        await coro
    except Exception as e:
        loop.call_exception_handler({'message': str(e), 'exception': e})


def get_remaining_tasks():
    tasks = asyncio.Task.all_tasks()
    return list(tasks)


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


async def cancel_remaining_tasks(futures=None, raise_exceptions=False, log_exceptions=None,
        log_tasks=False):

    log = logger.get_async(__name__, subname='cancel_remaining_tasks')

    if not futures:
        log.debug('Collecting Default Tasks')
        futures = asyncio.Task.all_tasks()

    futures = [
        task for task in futures
        if task is not asyncio.tasks.Task.current_task()
    ]

    def cancel_task(task):
        if not task.cancelled():
            if task.done():
                if task.exception():
                    # Need to find a more sustainable way of doing this, this makes
                    # sure that we are not raising exceptions for external tasks.
                    if not task_is_third_party(task):
                        if raise_exceptions:
                            raise task.exception()
                        elif log_exceptions:
                            log.warning(task.exception())
            else:
                task.cancel()
                if not task_is_third_party(task):
                    if log_tasks:
                        log.debug(f'Cancelled Task {task}')

    list(map(cancel_task, futures))
    await asyncio.gather(*futures, return_exceptions=True)

    return futures
