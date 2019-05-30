import asyncio
from cement import Interface

from instattack.lib.utils import (
    save_iteratively, save_concurrently, start_and_stop)

from instattack.app.mixins import LoggerMixin

from instattack.app.proxies.models import Proxy
from instattack.app.proxies.broker import ProxyBroker
from instattack.app.proxies.utils import scrape_proxies

from .abstract import InstattackController
from .utils import proxy_command


class ProxyInterface(Interface, LoggerMixin):

    class Meta:
        interface = 'user'

    async def _save_proxies(self, iterable, update_duplicates=False, ignore_duplicates=True):
        if self.app.pargs.concurrent:
            created, updated = await save_concurrently(
                iterable,
                ignore_duplicates=ignore_duplicates,
                update_duplicates=update_duplicates,
            )
        else:
            created, updated = await save_iteratively(
                iterable,
                ignore_duplicates=ignore_duplicates,
                update_duplicates=update_duplicates,
            )
        return created, updated


class ProxyController(InstattackController, ProxyInterface):

    class Meta:
        label = 'proxies'
        stacked_on = 'base'
        stacked_type = 'nested'

        interfaces = [
            ProxyInterface,
        ]

    @proxy_command(help="Clear Historical Error and Request History of Proxies")
    def clear_history(self):

        async def _clear_history():
            to_save = []
            async for proxy in Proxy.all():
                # Regular errors are translated on save currently.
                if proxy.errors != {} or proxy.active_errors != {} or proxy.num_requests != 0:
                    proxy.errors = {}
                    proxy.active_errors = {}
                    proxy.num_requests = 0
                    to_save.append(proxy)
            return to_save

        with start_and_stop("Clearing Proxy History") as spinner:
            loop = asyncio.get_event_loop()
            to_save = loop.run_until_complete(_clear_history())

            spinner.write(f"> Updating {len(to_save)} Proxies")
            loop.run_until_complete(self._save_proxies(
                to_save, update_duplicates=True, ignore_duplicates=True
            ))

    @proxy_command(help="Scrape Proxies and Save to DB", limit=True)
    def scrape(self):

        with start_and_stop("Scraping Proxies") as spinner:
            proxies = scrape_proxies(limit=self.limit)

            spinner.write(f"> Saving {len(proxies)} Scraped Proxies")
            loop = asyncio.get_event_loop()
            created, updated = loop.run_until_complete(self._save_proxies(proxies))

            spinner.write(f"> Created {len(created)} Proxies")
            spinner.write(f"> Updated {len(updated)} Proxies")

    @proxy_command(help="Collect Proxies w/ ProxyBroker and Save to DB", limit=True)
    def collect(self):

        async def _collect(broker):
            updated = []
            created = []
            async for proxy, was_created in broker.collect(loop, save=False):
                if was_created:
                    created.append(proxy)
                else:
                    updated.append(proxy)
            return updated, created

        with start_and_stop("Collecting Proxies") as spinner:

            broker = ProxyBroker(
                self.app.config,
                limit=self.app.pargs.limit,
            )

            loop = asyncio.get_event_loop()
            updated, created = loop.run_until_complete(_collect(broker))

            spinner.write(f"> Creating {len(created)} Proxies")
            loop.run_until_complete(self._save_proxies(created, update_duplicates=True))

            spinner.write(f"> Updating {len(updated)} Proxies")
            loop.run_until_complete(self._save_proxies(updated, update_duplicates=True))
