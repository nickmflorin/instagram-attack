import asyncio

from tortoise.transactions import in_transaction

from instattack.logger import AppLogger
from instattack.lib import validate_method


log = AppLogger(__name__)


async def stream_proxies(method, limit=None):
    from instattack.core.models.proxies import Proxy

    method = validate_method(method)
    qs = Proxy.filter(method=method).all()
    if limit:
        qs = qs.limit(limit)
    async for proxy in qs:
        yield proxy


async def find_proxy(proxy):
    from instattack.core.models.proxies import Proxy

    saved = await Proxy.filter(
        host=proxy.host,
        port=proxy.port,
        method=proxy.method,
    ).first()
    return saved


async def update_or_create_proxy(proxy):
    saved = await find_proxy(proxy)
    if saved:
        differences = saved.compare(proxy, return_difference=True)
        if differences:
            saved.avg_resp_time = proxy.avg_resp_time
            saved.error_rate = proxy.error_rate
            await saved.save()
        return False, differences
    else:
        await proxy.save()
        return True, None


async def remove_proxies(method):
    from instattack.core.models.proxies import Proxy
    log = AppLogger('Removing Proxies')

    async with in_transaction():
        async for proxy in Proxy.filter(method=method).all():
            log.info('Deleting Proxy', extra={'proxy': proxy})
            await proxy.delete()


async def update_or_create_proxies(method, proxies):

    log = AppLogger('Updating/Creating Proxies')

    tasks = []
    async with in_transaction():
        for proxy in proxies:
            task = asyncio.create_task(update_or_create_proxy(proxy))
            tasks.append(task)

    results = await asyncio.gather(*tasks)

    num_created = len([res for res in results if res[0]])
    num_updated = len([res for res in results if res[1] and not res[1].none])

    log.info(f'Created {num_created} {method} Proxies')
    log.info(f'Updated {num_updated} {method} Proxies')


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

                # If the future returned a result, schedule the remaining tasks
                # to be cancelled and return the result.
                if f.result():
                    asyncio.create_task(cancel_remaining_tasks(futures=futures))
                    return f.result()
                else:
                    if f.exception():
                        log.error(f.exception())

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
                    log.critical('Future Done')
                    futures.remove(f)
                    try:
                        newc = await coros.__anext__()
                        log.critical('Adding Future')
                        futures.append(asyncio.create_task(newc))
                    except StopIteration as e:
                        pass
                    log.critical('Returning Result')
                    return f.result()

    while len(futures) > 0 and not stop_event.is_set():
        log.critical('Yielding First to Finish')
        yield await first_to_finish()

    asyncio.create_task(cancel_remaining_tasks(futures=futures))


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
