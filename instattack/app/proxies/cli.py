import asyncio
from plumbum import cli

from instattack.lib import logger
from instattack.lib.utils import save_iteratively, save_concurrently

from instattack.app.entrypoint import EntryPoint, BaseApplication, SelectOperatorApplication

from .models import Proxy
from .broker import ProxyBroker
from .utils import scrape_proxies


@EntryPoint.subcommand('proxies')
class ProxyEntryPoint(BaseApplication):
    pass


class ProxyApplicationMixin(object):

    concurrent = cli.Flag("--concurrent", default=False)

    async def log_save_results(self, created, updated):
        log = logger.get_async(__name__, subname='log_save_results')

        if len(created) != 0:
            await log.success(f'Created {len(created)} Proxies')
        if len(updated) != 0:
            await log.success(f'Updated {len(updated)} Proxies')
        if len(updated) == 0 and len(created) == 0:
            await log.error('No Proxies to Update or Create')

    async def save_proxies(self, iterable, update_duplicates=False, ignore_duplicates=True):
        log = logger.get_async(__name__, subname='save_proxies')

        if self.concurrent:
            log.debug('Saving Concurrently')
            created, updated = await save_concurrently(
                iterable,
                ignore_duplicates=ignore_duplicates,
                update_duplicates=update_duplicates,
            )
        else:
            log.debug('Saving Iteratively')
            created, updated = await save_iteratively(
                iterable,
                ignore_duplicates=ignore_duplicates,
                update_duplicates=update_duplicates,
            )

        await self.log_save_results(created, updated)


class BaseProxy(BaseApplication, ProxyApplicationMixin):

    __group__ = 'Proxy Pool'

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop))


@ProxyEntryPoint.subcommand('clean')
class ProxyClean(SelectOperatorApplication, ProxyApplicationMixin):

    async def errors(self, loop):
        to_save = []
        async for proxy in Proxy.all():
            # Regular errors are translated on save currently.
            proxy.active_errors = {}
            to_save.append(proxy)

        await self.save_proxies(to_save, update_duplicates=True, ignore_duplicates=True)


@ProxyEntryPoint.subcommand('clear')
class ProxyClear(SelectOperatorApplication, ProxyApplicationMixin):

    async def history(self, loop):
        to_save = []
        async for proxy in Proxy.all():
            # Regular errors are translated on save currently.
            proxy.errors = {}
            proxy.active_errors = {}
            proxy.num_requests = 0
            to_save.append(proxy)

        await self.save_proxies(to_save, update_duplicates=True, ignore_duplicates=True)


@ProxyEntryPoint.subcommand('scrape')
class ProxyScrape(BaseProxy):

    limit = cli.SwitchAttr("--limit", int, mandatory=False,
        help="Limit the number of proxies to collect.")

    async def operation(self, loop):
        log = logger.get_async(__name__, subname='operation')

        message = 'Scraping Proxies...'
        if self.limit:
            message = f'Scraping Proxies w Limit = {self.limit}'
        await log.start(message)

        proxies = scrape_proxies(limit=self.limit)
        await log.complete(f'Scraped {len(proxies)} Proxies')

        await self.save_proxies(proxies)


@ProxyEntryPoint.subcommand('collect')
class ProxyCollect(BaseProxy):

    limit = cli.SwitchAttr("--limit", int, mandatory=True,
        help="Limit the number of proxies to collect.")

    async def operation(self, loop):

        config = self.config()
        broker = ProxyBroker(
            config['proxies']['broker'],
            limit=self.limit,
        )

        updated = []
        created = []
        async for proxy, was_created in broker.collect(loop, save=False):
            if was_created:
                created.append(proxy)
            else:
                updated.append(proxy)

        await self.save_proxies(created, update_duplicates=True)
        await self.save_proxies(updated, update_duplicates=True)
