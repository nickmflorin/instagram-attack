from __future__ import absolute_import

import asyncio
from collections import Iterable


def ensure_iterable(arg):
    if isinstance(arg, str):
        return [arg]
    elif not isinstance(arg, Iterable):
        return [arg]
    return arg


def convert_lines_to_text(lines):
    # This is being a pain about circular imports, will resolve later.
    from instattack.logger import AppLogger
    log = AppLogger(__file__)

    if "" in lines:
        log.warning('Found empty string in lines.')
    elif None in lines:
        log.warning('Found null value in lines.')

    lines = [line for line in lines if line is not None and line != ""]
    return "\n".join(lines)


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
