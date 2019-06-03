import asyncio
from tortoise.exceptions import IntegrityError

from .asyncio import ensure_async_generator


async def create_save_tasks(iterable):
    tasks = []
    gen = ensure_async_generator(iterable)
    async for proxy in gen:
        tasks.append(asyncio.create_task(proxy.save()))
    return tasks


async def save_iteratively(iterable):
    """
    TODO
    ----
    Incorporate progress bar optionality.
    """
    created = []
    updated = []
    async for item in ensure_async_generator(iterable):
        try:
            await item.save()
        except IntegrityError as e:
            # Temporarily Until We Figure Out How to Handle
            raise e
            # item = await item.update_existing()
            # updated.append(item)
        else:
            created.append(item)
    return created, updated


async def save_concurrently(iterable):
    """
    TODO
    ----
    Incorporate progress bar optionality.
    """
    tasks = await create_save_tasks(iterable)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    created = []
    updated = []
    for result in results:
        if isinstance(result, Exception):
            # Temporarily Until We Figure Out How to Handle
            raise result
            # if isinstance(result, IntegrityError):
            #     if not ignore_duplicates and not update_duplicates:
            #         raise result
            #     elif update_duplicates:

            #         # We will need to add this method for proxy collection.
            #         if not hasattr(result, 'update_existing'):
            #             raise RuntimeError('Must specify update method on model.')

            #         result = await result.update_existing()
            #         updated.append(result)
        else:
            created.append(result)

    return created, updated
