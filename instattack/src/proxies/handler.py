from instattack.src.base import HandlerMixin

from .broker import ProxyBroker
from .pool import ProxyPool


class ProxyHandler(HandlerMixin):

    __name__ = "Proxy Handler"

    def __init__(self, config, start_event=None, lock=None, **kwargs):
        """
        [x] TODO:
        ---------
        What would be really cool would be if we could pass in our custom pool
        directly so that the broker popoulated that queue with the proxies.
        """
        super(ProxyHandler, self).__init__()
        self.start_event = start_event
        self.lock = lock

        self.broker = ProxyBroker(config, **kwargs)
        self.pool = ProxyPool(config, self.broker,
            start_event=self.start_event)

    async def stop(self, loop):
        log = self.create_logger('stop', ignore_config=True)
        await log.stop('Stopping')

        if self.pool.should_collect:
            self.broker.stop(loop)
        await log.debug('Done Stopping Proxy Handler')

    async def run(self, loop):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.

        [x] TODO:
        ---------
        We are eventually going to need the relationship between prepopulation
        and collection to be more dynamic and adjust, and collection to trigger
        if we are running low on proxies.
        """
        log = self.create_logger('start', ignore_config=True)
        await log.start('Starting Proxy Handler')

        if self.pool.should_prepopulate:
            try:
                await log.debug('Prepopulating Proxy Pool...')
                await self.pool.prepopulate(loop)
            except Exception as e:
                raise e

        if self.pool.should_collect:
            # Pool will set start event when it starts collecting proxies.
            await self.pool.collect(loop)
        else:
            await log.debug('Not Collecting Proxies...')
            if self.start_event.is_set():
                raise RuntimeError('Start Event Already Set')

            self.start_event.set()
            await log.info('Setting Start Event', extra={
                'other': 'Proxy Pool Prepopulated'
            })
