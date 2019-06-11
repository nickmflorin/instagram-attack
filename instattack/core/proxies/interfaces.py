from instattack.core.exceptions import ProxyPoolError


class ProxyQueueInterface(object):

    @property
    def __queueid__(self):
        raise NotImplementedError()

    @property
    def __NAME__(self):
        raise NotImplementedError()

    async def contains(self, proxy):
        raise NotImplementedError()

    @property
    def num_proxies(self):
        return self.qsize()

    def validate_for_queue(self, proxy):
        raise NotImplementedError()

    def raise_for_queue(self, proxy):
        raise NotImplementedError()

    async def put(self, proxy, **kwargs):
        raise NotImplementedError()

    async def get(self):
        raise NotImplementedError()

    async def raise_if_missing(self, proxy):
        """
        Most likely a temporary utility.
        Raises ProxyPoolError if a proxy is expected in the queue but is not
        found.
        """
        if not await self.contains(proxy):
            raise ProxyPoolError(f'Expected Proxy to be in {self.__NAME__}')

    async def raise_if_present(self, proxy):
        """
        Most likely a temporary utility.
        Raises ProxyPoolError if a proxy is not expected in the queue but is
        found.
        """
        if await self.contains(proxy):
            raise ProxyPoolError(f'Did Not Expect Proxy to be in {self.__NAME__}')

    async def warn_if_missing(self, proxy):
        """
        Most likely a temporary utility.
        Warns if a proxy is expected in the queue but is not found.
        """
        try:
            await self.raise_if_missing(proxy)
        except ProxyPoolError as e:
            self.log.warning(e)
            return True
        else:
            return False

    async def warn_if_present(self, proxy):
        """
        Most likely a temporary utility.
        Warns if a proxy is not expected in the queue but is found.
        """
        try:
            await self.raise_if_present(proxy)
        except ProxyPoolError as e:
            self.log.warning(e)
            return True
        else:
            return False


class ProxyManagerInterface(object):

    @property
    def __NAME__(self):
        raise NotImplementedError()

    @property
    def num_proxies(self):
        return self.pool.qsize()

    async def stop(self):
        raise NotImplementedError()

    async def put(self, proxy, **kwargs):
        raise NotImplementedError()

    async def get(self):
        raise NotImplementedError()

    async def start(self, **kwargs):
        raise NotImplementedError()

    async def on_proxy_error(self, proxy, exc):
        raise NotImplementedError()

    async def on_proxy_success(self, proxy):
        raise NotImplementedError()
