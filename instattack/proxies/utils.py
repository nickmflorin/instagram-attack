import asyncio
from bs4 import BeautifulSoup
import requests
from tortoise.transactions import in_transaction

from instattack.logger import AppLogger
from instattack.lib import validate_method
from .models import Proxy


log = AppLogger(__name__)


def scrape_proxies(method='POST', scheme='HTTP'):
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
            if scheme.lower() == 'https' and is_https == 'yes':
                proxy = Proxy(
                    host=host,
                    port=port,
                    method=method,
                    schemes=['HTTPS'],
                    avg_resp_time=1.0,  # Guess for now?
                )
                proxies.append(proxy)
            elif scheme.lower() == 'http' and is_https == 'no':
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
