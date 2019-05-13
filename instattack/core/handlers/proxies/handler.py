import asyncio

from instattack.lib import starting, stopping

from instattack.core.handlers.base import MethodHandler

from .broker import CustomBroker
from .pool import CustomProxyPool


class ProxyHandler(MethodHandler):

    __name__ = 'Proxy Handler'

    def __init__(self, broker_config=None, pool_config=None, **kwargs):
        super(ProxyHandler, self).__init__(**kwargs)

        self._proxies = asyncio.Queue()
        self.broker = CustomBroker(self._proxies, config=broker_config, **kwargs)
        self.pool = CustomProxyPool(self._proxies, self.broker, config=pool_config, **kwargs)

    @starting
    async def run(self, loop, limit=None, **kwargs):
        """
        NOTE:
        -----
        When running concurrently with other tasks/handlers, we don't always
        want to shut down the proxy handler when we hit the limit, because
        the other handler might still be using those.
        """
        await asyncio.gather(
            self.broker.start(loop),
            self.pool.run(loop)
        )

    @stopping
    async def stop(self, loop):
        """
        The pool will stop on it's own, once it realizes that there are no
        more proxies in the broker.
        """
        if self._stopped:
            raise RuntimeError('Proxy Handler Already Stopped')

        self.broker.stop(loop)
        self._stopped = True

    async def get(self):
        return await self.pool.get()

    async def save(self, loop):
        return await self.pool.save(loop)
