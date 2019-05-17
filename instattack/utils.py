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


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]

    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    return tasks
