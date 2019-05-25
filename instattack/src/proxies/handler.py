from instattack import logger
from instattack.src.base import Handler

from .broker import ProxyBroker
from .pool import ProxyPool


class ProxyHandler(Handler):

    __name__ = "Proxy Handler"

    def __init__(self, config, **kwargs):
        """
        [x] TODO:
        ---------
        What would be really cool would be if we could pass in our custom pool
        directly so that the broker popoulated that queue with the proxies.
        """
        super(ProxyHandler, self).__init__(**kwargs)

        self.broker = ProxyBroker(
            config['broker'],
            **kwargs
        )

        self.pool = ProxyPool(
            config['pool'],
            self.broker,
            start_event=self.start_event,
        )

    async def stop(self, loop):
        log = logger.get_async(self.__name__, subname='stop')
        log.stop('Stopping')

        if self.pool.should_collect:
            self.broker.stop(loop)
        log.debug('Done Stopping Proxy Handler')

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
        log = logger.get_async(self.__name__, subname='start')
        log.start('Starting')

        if self.pool.should_prepopulate:
            try:
                log.debug('Prepopulating Pool...')
                await self.pool.prepopulate(loop)
            except Exception as e:
                raise e

        if self.pool.should_collect:
            await self.pool.collect(loop)
        else:
            log.debug('Not Collecting Proxies...')

            if self.start_event.is_set():
                raise RuntimeError('Start Event Already Set')

            self.start_event.set()
            log.info('Setting Start Event', extra={
                'other': 'Pool Prepopulated'
            })
