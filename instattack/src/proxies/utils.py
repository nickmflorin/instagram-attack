import asyncio
from bs4 import BeautifulSoup
import inspect
import requests

from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from instattack import logger
from .models import Proxy


def scrape_proxies(limit=None):
    """
    Not currently used, but could be useful.
    """
    url = "https://www.us-proxy.org/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')

    proxies = []
    table = soup.find_all('table', {'id': 'proxylisttable'})[0]
    rows = table.findChildren('tr')[1:]

    for row in rows:
        if limit and len(proxies) == limit:
            break

        children = row.findChildren('td')
        try:
            host = children[0].text
            port = children[1].text
            is_https = children[6].text
        except IndexError:
            break
        else:
            # We only want HTTP proxies.
            if is_https == 'no':
                proxy = Proxy(
                    host=host,
                    port=port,
                    avg_resp_time=0.1,  # Guess for now?
                )
                proxies.append(proxy)
    return proxies


async def stream_proxies():
    # We should start restricting the proxies we use more cleverly when
    # prepopulating.
    # async for proxy in Proxy.filter(method=method).all():
    async for proxy in Proxy.filter(invalid__not=1).all():
        yield proxy


async def find_proxy(proxy):

    saved = await Proxy.filter(
        host=proxy.host,
        port=proxy.port,
        method=proxy.method,
    ).first()
    return saved


async def save_proxies(proxies, concurrent=False, update=False):
    """
    Saves a series of proxies if they do not exist in the database, but DOES NOT
    update the proxies if new proxies are in the database with different values.

    Can pass in either a list of proxies or an async generator.

    TODO
    ----
    Include an `update` keyword argument and include logic in the Proxy.save()
    method that saves the proxy but if it hits an error from duplication it will
    conditionally update the older proxy with the newone that was provided.
    """
    log = logger.get_async('Saving Proxies')

    async def proxy_generator(proxy_iterable):
        if inspect.isasyncgen(proxy_iterable):
            async for proxy in proxy_iterable:
                yield proxy
        else:
            for proxy in proxy_iterable:
                yield proxy

    async def create_tasks(proxy_iterable):
        tasks = []
        async for proxy in proxy_generator(proxy_iterable):
            tasks.append(asyncio.create_task(proxy.save()))
        return tasks

    async def save_proxies_concurrently(proxy_iterable):

        num_saved = 0
        tasks = await create_tasks(proxy_iterable)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if not isinstance(result, Exception):
                num_saved += 1
        return num_saved

    async def save_proxies_iteratively(proxy_iterable):

        num_saved = 0
        async for proxy in proxy_generator(proxy_iterable):
            try:
                await proxy.save()
            except IntegrityError as e:
                log.error(e)
            else:
                num_saved += 1
        return num_saved

    if concurrent:
        await save_proxies_concurrently(proxies)
    else:
        await save_proxies_iteratively(proxies)


async def update_or_create_proxy(proxy):

    # TODO: Move this logic to the save method and include an update=False field
    saved = await find_proxy(proxy)
    if saved:
        differences = saved.compare(proxy, return_difference=True)
        if differences:
            await saved.update_from_differences(differences)
        return False, differences
    else:
        await proxy.save()
        return True, None


async def remove_proxies(method):
    log = logger.get_async('Removing Proxies')

    async with in_transaction():
        async for proxy in Proxy.filter(method=method).all():
            log.info('Deleting Proxy', extra={'proxy': proxy})
            await proxy.delete()


async def update_or_create_proxies(method, proxies):

    log = logger.get_async('Updating/Creating Proxies')

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
