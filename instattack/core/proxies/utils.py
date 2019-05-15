import asyncio

from tortoise.transactions import in_transaction

from instattack.logger import AppLogger
from instattack.lib import validate_method
from .models import Proxy


log = AppLogger(__name__)


async def stream_proxies(method):

    method = validate_method(method)
    async for proxy in Proxy.filter(method=method).all():
        yield proxy


async def find_proxy(proxy):

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
