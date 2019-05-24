import asyncio
from plumbum import cli

from instattack import logger
from instattack.lib import CustomProgressbar
from instattack.src.cli import EntryPoint, BaseApplication

from .models import Proxy
from .broker import InstattackProxyBroker
from .utils import scrape_proxies, save_proxies


@EntryPoint.subcommand('proxies')
class ProxyEntryPoint(BaseApplication):
    pass


class BaseProxy(BaseApplication):

    __group__ = 'Proxy Pool'

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop))


@ProxyEntryPoint.subcommand('clean')
class ProxyClean(BaseProxy):
    """
    Will be used to remove duplicate proxies that are saved.  Potentially also
    be used to update metrics if we get that far in this project.
    """
    async def operation(self):
        progress = CustomProgressbar(Proxy.count_all(), label='Cleaning Errors')
        progress.start()
        async for proxy in Proxy.all():
            proxy.errors = {}
            await proxy.save()

            progress.update()
        progress.finish()


@ProxyEntryPoint.subcommand('scrape')
class ProxyScrape(BaseProxy):

    limit = cli.SwitchAttr("--limit", int, mandatory=False,
        help="Limit the number of proxies to collect.")
    concurrent = cli.Flag("--concurrent", default=False)

    async def operation(self, loop):
        log = logger.get_sync(__name__, subname='operation')

        message = 'Scraping Proxies...'
        if self.limit:
            message = f'Scraping Proxies w Limit = {self.limit}'
        log.start(message)

        proxies = scrape_proxies(limit=self.limit)
        log.complete(f'Scraped {len(proxies)} Proxies')

        await save_proxies(proxies, concurrent=self.concurrent)


@ProxyEntryPoint.subcommand('collect')
class ProxyCollect(BaseProxy):

    limit = cli.SwitchAttr("--limit", int, mandatory=True,
        help="Limit the number of proxies to collect.")
    concurrent = cli.Flag("--concurrent", default=False)

    async def operation(self, loop):
        log = logger.get_async(__name__, subname='operation')

        config = self.config()
        broker = InstattackProxyBroker(
            config['proxies']['broker'],
            limit=self.limit,
        )

        log.start('Collecting Proxies...')
        async with broker.session(loop):
            updated = []
            created = []
            async for proxy, was_created in broker.collect(loop, save=False):
                if was_created:
                    created.append(proxy)
                else:
                    updated.append(proxy)

        await log.complete(f'Creating {len(created)} New Proxies')
        await save_proxies(created, concurrent=self.concurrent)

        await log.success(f'Saving {len(updated)} Updated Proxies')
        await save_proxies(updated, concurrent=self.concurrent)
