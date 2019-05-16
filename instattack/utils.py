import asyncio
from plumbum.path import LocalPath

from .logger import AppLogger


log = AppLogger(__name__)


def get_root():
    from .settings import APP_NAME
    parents = LocalPath(__file__).parents
    return [p for p in parents if p.name == APP_NAME][0].parent


def get_app_root():
    from .settings import APP_NAME
    root = get_root()
    return root / APP_NAME


def dir_str(path):
    return "%s/%s" % (path.dirname, path.name)


async def coro_exc_wrapper(coro, loop):
    try:
        await coro
    except Exception as e:
        loop.call_exception_handler({'message': str(e), 'exception': e})


async def limit_on_success(coros, batch_size, max_tries=None):
    """
    Runs single coroutine in batches until it returns a successful response or
    the number of attempts of the coroutine reaches the max limit.

    The batch number is maintained as tasks are finished and do not return
    the desired non-null result.
    """
    futures = []
    for i in range(batch_size):
        c = await coros.__anext__()
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
                        asyncio.create_task(cancel_remaining_tasks(futures=futures))
                        return f.result()
                    else:
                        futures.remove(f)
                        if not max_tries or attempts < max_tries:
                            try:
                                newc = await coros.__anext__()
                                futures.append(asyncio.create_task(newc))
                            except StopIteration as e:
                                pass


async def limit_as_completed(coros, batch_size, stop_event=None):
    """
    Takes a generator yielding coroutines and runs the coroutines concurrently,
    similarly to asyncio.as_completed(tasks), except that it limits the number
    of concurrent tasks at any given time, specified by `batch_size`.

    When coroutines complete, and the pool of concurrent tasks drops below the
    batch_size, coroutines will be added to the batch until there are none left.and
    """
    futures = []
    for i in range(batch_size):
        c = await coros.__anext__()
        futures.append(asyncio.create_task(c))

    async def first_to_finish():
        while True:
            await asyncio.sleep(0)
            for f in futures:
                if f.done():
                    log.debug('Future Done')
                    if f.exception():
                        raise f.exception()
                    else:
                        log.debug('Removing Future')
                        futures.remove(f)
                        try:
                            newc = await coros.__anext__()
                            log.debug('Adding Future')
                            futures.append(asyncio.create_task(newc))
                        except StopIteration as e:
                            pass
                        log.debug('Future Has Result')
                        return f.result()

    while len(futures) > 0 and not stop_event.is_set():
        log.debug('Yielding')
        yield first_to_finish()

    asyncio.create_task(cancel_remaining_tasks(futures=futures))


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]

    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    return tasks
