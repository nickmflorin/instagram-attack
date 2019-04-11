from __future__ import absolute_import

import asyncio
import contextlib


async def cancel_remaining_tasks(futures):
    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)


class AsyncTaskManager(contextlib.AbstractAsyncContextManager):

    def __init__(self, stop_event, tasks=None, log=None):
        self.log = log
        self.stop_event = stop_event
        self.tasks = tasks or []

    def add(self, task):
        self.tasks.append(task)

    async def notify(self, message):
        if self.log:
            self.log.warning(message)

    async def stop(self):
        await self.notify('Setting Stop Event')
        self.stop_event.set()

    async def __aenter__(self):
        while not self.stop_event.is_set():
            return self

    async def __aexit__(self, exc_type, exc_value, tb):
        """
        If the context block leaves before .stop() is called, we don't want
        to hit an error because there are no tasks.
        """
        if self.tasks:
            await self.notify("Cleaning up remaining tasks...")
            asyncio.ensure_future(cancel_remaining_tasks(self.tasks))
        return True
