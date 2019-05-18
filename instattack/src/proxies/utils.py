import asyncio
from bs4 import BeautifulSoup
import requests
from tortoise.transactions import in_transaction

from instattack.logger import AsyncLogger
from instattack.conf.utils import validate_method
from .models import Proxy


def scrape_proxies(method='POST'):
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
                    method=method, schemes=['HTTP'],
                    avg_resp_time=1.0,  # Guess for now?
                )
                proxies.append(proxy)
    return proxies


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
            await saved.update_from_differences(differences)
        return False, differences
    else:
        await proxy.save()
        return True, None


async def remove_proxies(method):
    log = AsyncLogger('Removing Proxies')

    async with in_transaction():
        async for proxy in Proxy.filter(method=method).all():
            log.info('Deleting Proxy', extra={'proxy': proxy})
            await proxy.delete()


async def update_or_create_proxies(method, proxies):

    log = AsyncLogger('Updating/Creating Proxies')

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
