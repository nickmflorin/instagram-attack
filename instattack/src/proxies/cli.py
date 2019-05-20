import asyncio
from plumbum import cli

from instattack.lib import CustomProgressbar
from instattack.src.exceptions import ArgumentError

from instattack.src.cli import EntryPoint, BaseApplication

from .models import Proxy
from .broker import InstattackProxyBroker
from .utils import scrape_proxies, save_proxies


@EntryPoint.subcommand('proxies')
class BaseProxy(BaseApplication):

    __group__ = 'Proxy Pool'


@BaseProxy.subcommand('clean')
class ProxyClean(BaseProxy):
    """
    Will be used to remove duplicate proxies that are saved.  Potentially also
    be used to update metrics if we get that far in this project.
    """

    def main(self, arg):
        loop = asyncio.get_event_loop()
        if arg == 'errors':
            loop.run_until_complete(self.clean_errors())
        else:
            raise ArgumentError(f'Invalid argument {arg}.')

    async def clean_errors(self):
        progress = CustomProgressbar(Proxy.count_all(), label='Cleaning Errors')
        progress.start()
        async for proxy in Proxy.all():
            proxy.errors = {}
            await proxy.save()

            progress.update()
        progress.finish()


@BaseProxy.subcommand('scrape')
class ProxyScrape(BaseProxy):

    limit = cli.SwitchAttr("--limit", int, mandatory=False,
        help="Limit the number of proxies to collect.")
    concurrent = cli.Flag("--concurrent", default=False)

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.scrape())

    async def scrape(self):
        if self.limit:
            self.log.start(f'Scraping Proxies w Limit = {self.limit}')
        else:
            self.log.start('Scraping Proxies...')
        proxies = scrape_proxies(limit=self.limit)
        self.log.complete(f'Scraped {len(proxies)} Proxies')

        await save_proxies(proxies, concurrent=self.concurrent)


@BaseProxy.subcommand('collect')
class ProxyCollect(BaseProxy):

    limit = cli.SwitchAttr("--limit", int, mandatory=True,
        help="Limit the number of proxies to collect.")
    concurrent = cli.Flag("--concurrent", default=False)

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.collect(loop))

    async def collect(self, loop):
        broker = InstattackProxyBroker(
            self.config['proxies']['broker'],
            limit=self.limit,
        )

        async with broker.session(loop):
            await save_proxies(broker.collect(), concurrent=self.concurrent)
