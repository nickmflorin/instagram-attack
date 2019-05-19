from instattack import logger
from instattack.lib import starting
from instattack.src.base import HandlerMixin

from .utils import stream_proxies, update_or_create_proxies
from .queue import ProxyPriorityQueue


log = logger.get_async('Proxy Pool')


class InstattackProxyPool(ProxyPriorityQueue, HandlerMixin):

    __name__ = 'Proxy Pool Queue'

    def __init__(self, config, broker, **kwargs):
        self.engage(**kwargs)

        super(InstattackProxyPool, self).__init__(config)

        self.broker = broker

        self.should_collect = config.get('collect', True)
        self.should_prepopulate = config.get('prepopulate', True)
        self.prepopulate_limit = config.get('prepopulate_limit')

    async def save(self, loop):
        """
        Saves proxies in the pool to the database.  This includes both proxies
        that were prepopulated and proxies that were collected from the broker,
        because we may need to update stats of proxies that were prepopulated.
        """
        proxies = []
        while not self.empty():
            ret = await super(ProxyPriorityQueue, self).get()
            proxy = ret[1]

            # Should we Still Save Removed Proxies?
            # mapped = self.proxy_finder[proxy.unique_id]
            # if mapped is not self.REMOVED:
            proxies.append(proxy)

        if len(proxies) == 0:
            log.error('No Proxies to Save')
            return

        await update_or_create_proxies(proxies)

    @starting('Proxy Prepopulation')
    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.

        NOTE:
        ----
        Unlike the broker case, we can't run the loop/generator while
            >>> len(futures) <= some limit

        So we don't pass the limit into stream_proxies and only add futures if
        the limit is not reached.
        """

        # Note:
        # The generator here seems to crap out when iterating over the larger
        # values > 500 (well not crap out, but not even start).  For now, we will
        # just hardcode a maximum prepopulate limit, since it is not specified
        # for the POST case.
        # Instead of doing:
        # >>> max_limit = len(await Proxy.filter(method=self.__method__).all())

        async for proxy in stream_proxies():
            if self.prepopulate_limit:
                if not self.qsize() < self.prepopulate_limit:
                    break

            # Proxy Filtered to be Valid or Non Confirmed
            proxy.reset()
            await self.put(proxy, source='Database')

        if self.qsize() == 0:
            log.error('No Proxies to Prepopulate')
            return

        log.complete(f"Prepopulated {self.qsize()} Proxies")

    @starting('Proxy Collection')
    async def collect(self, loop):
        """
        Retrieves proxies from the broker and converts them to our Proxy model.
        The proxy is then evaluated as to whether or not it meets the standards
        specified and conditionally added to the pool.

        TODO:
        ----
        We should maybe make this more dynamic, and add proxies from the broker
        when the pool drops below the limit.
        """
        # collect_limit = max(self._maxsize - self.qsize(), 0)
        # if collect_limit == 0:
        #     self.issue_start_event('No Proxies to Collect')
        #     return

        # self.log_async.debug(f'Number of Proxies to Collect: {collect_limit}.')

        added = []
        # while len(added) < collect_limit:
        async for proxy in self.broker.collect():
            added_proxy = await self.put(proxy, source='Broker')
            if added_proxy:
                added.append(added_proxy)

                # Set Start Event on First Proxy Retrieved from Broker
                if self.start_event and not self.start_event.is_set():
                    self.issue_start_event('Broker Started Sending Proxies')
