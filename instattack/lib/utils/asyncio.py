import asyncio
import inspect

from instattack import settings
from instattack.lib import logger


def task_is_third_party(task):
    """
    Need to find a more sustainable way of doing this, this makes
    sure that we are not raising exceptions for external tasks.
    """
    directory = get_task_path(task)
    return not directory.startswith(settings.APP_DIR)


def get_coro_path(coro):
    return coro.cr_code.co_filename


def get_task_path(task):
    return get_coro_path(task._coro)


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


async def cancel_remaining_tasks(futures=None, raise_exceptions=False, log_exceptions=None, log_tasks=False):
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
