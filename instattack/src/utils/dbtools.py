import asyncio
from tortoise.exceptions import IntegrityError

from instattack import logger
from .asyncio import ensure_async_generator


async def create_save_tasks(iterable):
    tasks = []
    gen = ensure_async_generator(iterable)
    async for proxy in gen:
        tasks.append(asyncio.create_task(proxy.save()))
    return tasks


async def save_iteratively(iterable,
        ignore_duplicates=False, update_duplicates=False, log_duplicates=False):
    log = logger.get_async(__name__, subname='save_iteratively')

    created = []
    updated = []
    async for item in ensure_async_generator(iterable):
        try:
            await item.save()
        except IntegrityError as e:
            if not ignore_duplicates and not update_duplicates:
                raise e
            elif update_duplicates:

                # We will need to add this method for proxy collection.
                if not hasattr(item, 'update_existing'):
                    raise RuntimeError('Must specify update method on model.')

                item = await item.update_existing()
                updated.append(item)
            elif log_duplicates:
                # We might want to not log all of these warnings all the time.
                log.warning(e)
        else:
            created.append(item)
    return created, updated


async def save_concurrently(iterable,
        ignore_duplicates=False, update_duplicates=False, log_duplicates=False):

    log = logger.get_async(__name__, subname='save_concurrently')

    tasks = await create_save_tasks(iterable)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    created = []
    updated = []
    for result in results:
        if isinstance(result, Exception):
            if isinstance(result, IntegrityError):
                if not ignore_duplicates and not update_duplicates:
                    raise result
                elif update_duplicates:

                    # We will need to add this method for proxy collection.
                    if not hasattr(result, 'update_existing'):
                        raise RuntimeError('Must specify update method on model.')

                    result = await result.update_existing()
                    updated.append(result)
                elif log_duplicates:
                    # We might want to not log all of these warnings all the time.
                    log.warning(result)
        else:
            created.append(result)

    return created, updated
