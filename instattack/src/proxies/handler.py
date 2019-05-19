import asyncio

from instattack.lib import starting
from instattack.src.base import Handler

from .broker import InstattackProxyBroker
from .pool import InstattackProxyPool


class ProxyHandler(Handler):
    """
    Imports and gives proxies from queue on demand.
    We might not even need to inherit from the ProxyPool anymore... just the
    method handler.
    """
    __name__ = "Proxy Handler"
    REMOVED = '<removed-proxy>'

    def __init__(self, config, **kwargs):
        super(ProxyHandler, self).__init__(**kwargs)

        self.broker = InstattackProxyBroker(
            config['proxies']['broker'],
            **kwargs
        )

        # !! TODO:
        # What would be really cool would be if we could pass in our custom pool
        # directly so that the broker popoulated that queue with the proxies.
        self.pool = InstattackProxyPool(
            config['proxies']['pool'],
            self.broker,
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
