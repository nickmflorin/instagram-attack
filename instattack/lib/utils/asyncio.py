import asyncio
import inspect

from .paths import task_is_third_party


def isCoroutine(func):
    return asyncio.iscoroutinefunction(func)


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


async def limit_as_completed(coros, batch_size, stop_event=None):
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

    while len(futures) > 0 and (stop_event is None or not stop_event.is_set()):
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
                    yield f.result(), num_tries, futures


async def cancel_remaining_tasks(futures=None):

    futures = futures or asyncio.Task.all_tasks()
    futures = [
        task for task in futures
        if task is not asyncio.tasks.Task.current_task()
    ]

    async def cancel_task(task):
        if not task.done():
            if not task.cancelled():
                # We have to wrap this in a try-except because of race conditions
                # where the task might be completed by the time we get to this
                # point.
                try:
                    task.cancel()
                except asyncio.CancelledError:
                    pass
                else:
                    if not task_is_third_party(task):
                        raise task.exception()
        else:
            if task.exception():
                # Need to find a more sustainable way of doing this, this makes
                # sure that we are not raising exceptions for external tasks.
                if not task_is_third_party(task):
                    raise task.exception()

    coros = [cancel_task(task) for task in futures]
    await asyncio.gather(*coros, return_exceptions=True)

    return futures
