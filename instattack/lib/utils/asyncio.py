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


async def limit_as_completed(
    coros,
    batch_size,
    stop_callback=None,
    done_callback=None,
    stop_event=None,
):
    """
    Takes a generator yielding coroutines and runs the coroutines concurrently,
    similarly to asyncio.as_completed(tasks), except that it limits the number
    of concurrent tasks at any given time, specified by `batch_size`.

    When coroutines complete, and the pool of concurrent tasks drops below the
    batch_size, coroutines will be added to the batch until there are none left.and

    [!] IMPORTANT:
    --------------
    For whatever reason, using StopAsyncIteration was not working properly,
    especially in cases where the number of coroutines yielded from coros is
    less than the batch size.  The only other solution I could think of right
    now is to set a timeout, since the generator should be creating the tasks
    at a high frequency.

    Note sure why StopAsyncIteration works below though?
    """
    pending = []
    while len(pending) < batch_size:
        try:
            c = await asyncio.wait_for(coros.__anext__(), timeout=2.0)
            pending.append(asyncio.create_task(c))
        # except StopAsyncIteration as e:
        except asyncio.TimeoutError:
            break

    num_tries = 0
    while len(pending) > 0 and (not stop_event or not stop_event.is_set()):
        await asyncio.sleep(0)  # Not sure why this is necessary but it is.
        for f in pending:
            if f.done():
                num_tries += 1
                pending.remove(f)
                try:
                    newc = await coros.__anext__()
                    pending.append(asyncio.create_task(newc))
                except StopAsyncIteration as e:
                    pass

                yield f, pending, num_tries

                if done_callback:
                    done_callback(f, pending, num_tries)

                if stop_callback:
                    if stop_callback(f, pending, num_tries):
                        break


async def cancel_remaining_tasks(futures=None):

    futures = futures or asyncio.all_tasks()
    futures = [
        task for task in futures
        if task is not asyncio.tasks.current_task()
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
