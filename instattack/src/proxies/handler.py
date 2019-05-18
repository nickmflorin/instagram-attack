import asyncio

from instattack.lib import starting
from instattack.src.base import MethodHandler

from .broker import InstattackProxyBroker
from .pool import InstattackProxyPool


class ProxyHandler(MethodHandler):
    """
    Imports and gives proxies from queue on demand.
    We might not even need to inherit from the ProxyPool anymore... just the
    method handler.
    """
    __name__ = "Proxy Handler"
    REMOVED = '<removed-proxy>'

    def __init__(self, config, **kwargs):
        super(ProxyHandler, self).__init__(**kwargs)

        self.proxies = asyncio.Queue()
        self.broker = InstattackProxyBroker(config, self.proxies, **kwargs)

        # !! TODO:
        # What would be really cool would be if we could pass in the pool
        # directly to the broker so that the broker populated our custom pool
        # with our custom ProxyModel's.
        self.pool = InstattackProxyPool(
            config,
            self.proxies,
            self.broker,
            method=kwargs['method'],
            start_event=self.start_event,
        )

    @starting
    async def run(self, loop):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.
        """
        def collection_done(fut):
            if fut.exception():
                raise fut.exception()
            else:
                # Broker can be stopped if the token was received already.
                if not self.broker._stopped:
                    self.broker.stop(loop)

        if self.pool.should_prepopulate:
            try:
                self.log_async.debug('Prepopulating Pool...')
                await self.pool.prepopulate(loop)
            except Exception as e:
                raise e

        if self.pool.should_collect:
            asyncio.create_task(self.broker.start(loop))

            collection_task = asyncio.create_task(self.pool.collect(loop))
            collection_task.add_done_callback(collection_done)
        else:
            self.issue_start_event('Prepopulated Proxies Done')
