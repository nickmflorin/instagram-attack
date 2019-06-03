import asyncio
from cement import Interface
import tortoise

from instattack.lib.utils import (
    save_iteratively, save_concurrently, start_and_stop)

from instattack.app.mixins import LoggerMixin

from instattack.app.models import Proxy

from instattack.app.proxies import ProxyBroker
from instattack.app.proxies.utils import scrape_proxies

from instattack.app.handlers import TrainHandler

from .abstract import InstattackController
from .utils import proxy_command


class ProxyInterface(Interface, LoggerMixin):

    class Meta:
        interface = 'user'

    async def _save_proxies(self, iterable):
        if self.app.pargs.concurrent:
            created, updated = await save_concurrently(iterable)
        else:
            created, updated = await save_iteratively(iterable)
        return created, updated

    def get_proxies(self):

        async def _get_proxies():
            return await Proxy.all()
        return self.loop.run_until_complete(_get_proxies())

    def get_duplicates(self):

        duplicates = {}

        proxies = self.get_proxies()
        for proxy in proxies:
            duplicates.setdefault((proxy.host, proxy.port), [])
            duplicates[(proxy.host, proxy.port)].append(proxy)

        to_remove = []
        for key, val in duplicates.items():
            if len(val) == 1:
                to_remove.append(key)

        for key in to_remove:
            del duplicates[key]
        return duplicates

    def create_proxies(self, proxy_args):
        """
        Creates new proxies based on a list of proxy attributes which must at
        a minimum contain `host`, `port` and `avg_resp_time`.

        >>> [{'host': '0.0.0.0', 'port': 80, 'avg_resp_time': 1.0}, ...]
        """
        async def _create_proxies():
            created = []
            for proxy in proxy_args:
                try:
                    Proxy.get(host=proxy['host'], port=proxy['port'])
                except tortoise.exceptions.DoesNotExist:
                    proxy = await Proxy.create(**proxy)
                    created.append(proxy)
            return created

        created = self.loop.run_until_complete(_create_proxies())
        return created


class ProxyController(InstattackController, ProxyInterface):

    class Meta:
        label = 'proxies'
        stacked_on = 'base'
        stacked_type = 'nested'

        interfaces = [
            ProxyInterface,
        ]

    @proxy_command(help="Clear Historical Error and Request History of Proxies")
    def migrate_history(self):

        async def _migrate_history():
            to_save = []
            async for proxy in Proxy.all():
                proxy.active_errors = {}
                if proxy.errors:
                    proxy.errors = proxy.errors['all']
                    if proxy.errors.get('most_recent'):
                        proxy.last_error = proxy.errors['most_recent']
                to_save.append(proxy)
            return to_save

        with start_and_stop("Migrating Proxy History") as spinner:
            loop = asyncio.get_event_loop()
            to_save = loop.run_until_complete(_migrate_history())

            spinner.write(f"> Updating {len(to_save)} Proxies")
            loop.run_until_complete(self._save_proxies(to_save))

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
            loop.run_until_complete(self._save_proxies(to_save))

    @proxy_command(help="Scrape Proxies and Save to DB", limit=True)
    def train(self):
        train = TrainHandler(self.loop)

        # Right now there are no results
        result = self.loop.run_until_complete(train.train(limit=self.app.pargs.limit))
        print(result)

    @proxy_command(help="Scrape Proxies and Save to DB", limit=True)
    def scrape(self):

        with start_and_stop("Scraping Proxies") as spinner:
            proxy_args = scrape_proxies(limit=self.app.pargs.limit)

            proxies = self.get_proxies()
            spinner.write(f"Currently {len(proxies)} Proxies")

            # Have to Set a Default Value for Average Response Time for Now
            for proxy in proxy_args:
                proxy['avg_resp_time'] = 0.1

            spinner.write(f"Scraped {len(proxy_args)} Proxies")
            created = self.create_proxies(proxy_args)

            spinner.indent()
            if len(created) != 0:
                spinner.write(f"Created {len(created)} Proxies", success=True)

                proxies = self.get_proxies()
                spinner.write(f"Now {len(proxies)} Proxies")
            else:
                spinner.write('No New Proxies from Scrape', failure=True)

    @proxy_command(help="Check for Duplicate Proxies in Database")
    def check_duplicates(self):
        """
        We think that duplicates are coming about because the unique fields
        on the proxy model were never created for the given table, and we would
        have to migrate the current proxies to another temporary table to
        fix the problem.
        """
        duplicates = self.get_duplicates()
        if len(duplicates) == 0:
            self.success('No Duplicate Proxies')
        else:
            self.failure(f"{len(duplicates)} Duplicate Proxies")

    @proxy_command(help="Remove Duplicate Proxies in Database")
    def remove_duplicates(self):
        """
        We think that duplicates are coming about because the unique fields
        on the proxy model were never created for the given table, and we would
        have to migrate the current proxies to another temporary table to
        fix the problem.
        """
        duplicates = self.get_duplicates()
        if len(duplicates) == 0:
            self.failure('No Duplicates to Remove')
            return

        with start_and_stop(f"Deleting {len(duplicates)} Duplicates"):

            tasks = []
            for key, dups in duplicates.items():
                chronologically_ordered = sorted(dups, key=lambda dup: dup.date_added)
                for proxy in chronologically_ordered[1:]:
                    tasks.append(proxy.delete())

            self.loop.run_until_complete(asyncio.gather(*tasks))

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
            loop.run_until_complete(self._save_proxies(created))

            spinner.write(f"> Updating {len(updated)} Proxies")
            loop.run_until_complete(self._save_proxies(updated))
