import asyncio
from plumbum import cli

from instattack.lib import CustomProgressbar
from instattack.src.exceptions import ArgumentError

from instattack.src.proxies import ProxyHandler, Proxy
from instattack.src.proxies.exceptions import PoolNoProxyError
from instattack.src.proxies.utils import remove_proxies, scrape_proxies

from .base import EntryPoint, BaseApplication


@EntryPoint.subcommand('proxies')
class BaseProxy(BaseApplication):

    __group__ = 'Proxy Pool'
    _method = 'GET'

    @cli.switch("--method", cli.Set("GET", "POST", case_sensitive=False))
    def method(self, method):
        self._method = method.upper()


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


@BaseProxy.subcommand('remove')
class ProxyRemove(BaseProxy):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(remove_proxies(self._method))


@BaseProxy.subcommand('scrape')
class ProxyScrape(BaseProxy):

    def main(self):

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.scrape())

    async def scrape(self):
        tasks = []
        proxies = scrape_proxies(method=self._method, scheme='http')
        for proxy in proxies:
            task = asyncio.create_task(proxy.save())
            tasks.append(task)

        await asyncio.gather(*tasks)


@BaseProxy.subcommand('collect')
class ProxyCollect(BaseProxy):

    def main(self):
        loop = asyncio.get_event_loop()

        # Not really needed for this case but is needed for other cases that
        # depend on the handler pool.
        start_event = asyncio.Event()
        lock = asyncio.Lock()

        config = self.config.override(**{
            'login': {
                'proxies': {
                    'prepopulate': False,
                    'collect': True,
                }
            }
        })

        handler = ProxyHandler(
            method=self._method,
            lock=lock,
            start_event=start_event,
            config=config
        )

        loop.run_until_complete(self.collect(loop, handler))

    async def collect(self, loop, handler):
        try:
            await handler.run(loop)
        except PoolNoProxyError as e:
            self.log.error(e)
        finally:
            await handler.save(loop)
