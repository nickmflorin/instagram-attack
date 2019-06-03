from instattack.config import config

from instattack.app.proxies import ProxyBroker

from .base import Handler


class ProxyHandler(Handler):

    async def stop(self):
        pass

    async def run(self, limit=None):
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
        log = self.create_logger('start')
        await log.start(f'Starting {self.__name__}')

        try:
            await log.debug('Prepopulating Proxy Pool...')
            await self.pool.prepopulate(limit=limit)
        except Exception as e:
            raise e


class BrokeredProxyHandler(ProxyHandler):

    __name__ = "Proxy Broker Handler"

    def __init__(self, loop, pool_cls=None, **kwargs):
        """
        [x] TODO:
        ---------
        We need to use the stop event to stop the broker just in case an authenticated
        result is found.

        What would be really cool would be if we could pass in our custom pool
        directly so that the broker popoulated that queue with the proxies.
        """
        super(BrokeredProxyHandler, self).__init__(loop, **kwargs)
        self.broker = ProxyBroker(loop)
        self.pool = pool_cls(loop, self.broker, start_event=self.start_event)

    async def stop(self):
        if self.broker._started:
            self.broker.stop()

    async def run(self, limit=None):
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
        log = self.create_logger('start')
        await super(BrokeredProxyHandler, self).run(limit=limit)

        if config['pool']['collect']:
            # Pool will set start event when it starts collecting proxies.
            await self.pool.collect()
        else:
            if self.start_event.is_set():
                raise RuntimeError('Start Event Already Set')

            self.start_event.set()
            await log.info('Setting Start Event', extra={
                'other': 'Proxy Pool Prepopulated'
            })


class SimpleProxyHandler(ProxyHandler):

    __name__ = "Proxy Train Handler"

    def __init__(self, loop, pool_cls=None, **kwargs):
        super(SimpleProxyHandler, self).__init__(loop, **kwargs)
        self.pool = pool_cls(loop, start_event=self.start_event)
