import asyncio


async def coro_exc_wrapper(coro, loop):
    try:
        await coro
    except Exception as e:
        loop.call_exception_handler({'message': str(e), 'exception': e})


def get_remaining_tasks():
    tasks = asyncio.Task.all_tasks()
    return list(tasks)


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    def cancel_task(task):
        if not task.cancelled():
            if task.done():
                if task.exception():
                    raise task.exception()
            else:
                task.cancel()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]

    list(map(cancel_task, tasks))

    await asyncio.gather(*tasks, return_exceptions=True)
    return tasks
