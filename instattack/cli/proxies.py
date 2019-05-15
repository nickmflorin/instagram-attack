import asyncio
from plumbum import cli

from instattack.lib import CustomProgressbar
from instattack.exceptions import ArgumentError

from instattack.core.proxies.exceptions import PoolNoProxyError
from instattack.core.proxies import ProxyHandler, Proxy
from instattack.core.proxies.utils import remove_proxies

from .base import Instattack, BaseApplication


@Instattack.subcommand('proxies')
class ProxyApplication(BaseApplication):

    __group__ = 'Proxy Pool'
    _method = 'GET'

    @cli.switch("--method", cli.Set("GET", "POST", case_sensitive=False))
    def method(self, method):
        self._method = method.upper()


@ProxyApplication.subcommand('test')
class ProxyTest(ProxyApplication):
    """
    Will be used to test proxies against simple request URLs.
    Not sure if we will maintain this.
    """
    pass


@ProxyApplication.subcommand('clean')
class ProxyClean(ProxyApplication):
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


@ProxyApplication.subcommand('remove')
class ProxyRemove(ProxyApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(remove_proxies(self._method))


@ProxyApplication.subcommand('collect')
class ProxyCollect(ProxyApplication):

    def main(self):
        loop = asyncio.get_event_loop()

        # Not really needed for this case but is needed for other cases that
        # depend on the handler pool.
        start_event = asyncio.Event()
        lock = asyncio.Lock()

        config = self.config.override(**{
            'token': {
                'proxies': {
                    'prepopulate': False,
                    'collect': True,
                }
            },
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
