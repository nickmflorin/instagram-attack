import asyncio
from plumbum import cli

from lib import CustomProgressbar, log_handling

from instattack.exceptions import ArgumentError, PoolNoProxyError

from instattack.models import Proxy, ProxyError
from instattack.handlers import ProxyHandler

from .args import ProxyArgs
from .base import Instattack, BaseApplication


@Instattack.subcommand('proxies')
class ProxyApplication(BaseApplication, ProxyArgs):

    __group__ = 'Proxy Pool'
    _method = 'GET'

    @cli.switch("--method", cli.Set("GET", "POST", case_sensitive=False))
    def method(self, method):
        self._method = method.upper()


@ProxyApplication.subcommand('test')
class ProxyTest(ProxyApplication):
    """
    Will be used to test proxies against simple request URLs.
    """
    pass


@ProxyApplication.subcommand('clean')
class ProxyClean(ProxyApplication):
    """
    Will be used to remove duplicate proxies that are saved.  Potentially also
    be used to update metrics if we get that far in this project.
    """
    @log_handling('self')
    def main(self, arg):
        with self.loop_session() as loop:
            if arg == 'errors':
                loop.run_until_complete(self.clean_errors())
            else:
                raise ArgumentError(f'Invalid argument {arg}.')

    async def clean_errors(self):
        progress = CustomProgressbar(ProxyError.count(), label='Cleaning Errors')
        progress.start()
        async for error in ProxyError.all():
            await error.delete()
            progress.update()
        progress.finish()


@ProxyApplication.subcommand('collect')
class ProxyCollect(ProxyApplication):

    # Only applicable if --show is False (i.e. we are saving).
    clear = cli.Flag("--clear")

    @log_handling('self')
    def main(self):
        with self.loop_session() as loop:

            # Not really needed for this case but is needed for other cases that
            # depend on the handler pool.
            start_event = asyncio.Event()
            lock = asyncio.Lock()

            handler = ProxyHandler(
                method=self._method,
                lock=lock,
                start_event=start_event,
                **self.proxy_config(method=self._method),
            )
            loop.run_until_complete(self.collect(loop, handler))

    async def collect(self, loop, handler):
        try:
            await handler.run(loop, prepopulate=False, save=True)
        except PoolNoProxyError as e:
            self.log.error(e)
        finally:
            await handler.stop(loop)
