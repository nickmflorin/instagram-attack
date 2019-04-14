from __future__ import absolute_import

import asyncio
import logbook


__all__ = ('cancel_remaining_tasks', 'shutdown', )


async def cancel_remaining_tasks(futures):
    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)


async def shutdown(loop, signal=None, log=None):
    log = log or logbook.Logger("Shutdown")

    if signal:
        log.info(f'Received exit signal {signal.name}...')

    tasks = [task for task in asyncio.Task.all_tasks() if task is not
         asyncio.tasks.Task.current_task()]

    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info('Finished awaiting cancelled tasks, results.')
    loop.stop()
