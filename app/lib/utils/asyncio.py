from __future__ import absolute_import

import asyncio


__all__ = ('cancel_remaining_tasks', )


async def cancel_remaining_tasks(futures):
    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
