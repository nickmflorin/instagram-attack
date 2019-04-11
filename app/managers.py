from __future__ import absolute_import

import asyncio


class ProxyManager(object):

    def __init__(self, generated=None, good=None, handled=None):
        self.generated = generated or asyncio.Queue()
        self.good = good or asyncio.Queue()
        self.handled = handled or asyncio.Queue()

    async def get_best(self):
        # We could run into race conditions here - we may want to have a try
        # except.
        if not self.good.empty():
            return await self.good.get()
        return await self.handled.get()


class PasswordManager(object):

    def __init__(self, generated=None, attempted=None):
        self.generated = generated or asyncio.Queue()
        self.attempted = attempted or asyncio.Queue()


class QueueManager(object):

    def __init__(self, **kwargs):
        self.proxies = ProxyManager(**kwargs.get('proxies', {}))
        self.passwords = PasswordManager(**kwargs.get('passwords', {}))
