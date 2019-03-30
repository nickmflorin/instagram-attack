from __future__ import absolute_import

import logging

import asyncio
import queue

from app import settings
from app.lib.api import ProxyApi


__all__ = ('QueueManagerSync', 'QueueManagerAsync', )


class QueueManagerSync(object):

    def __init__(self, user):
        self.user = user

        self.proxies = queue.LifoQueue()
        self.tokens = queue.Queue()
        self.passwords = queue.Queue()

    @property
    def queues(self):
        return {
            'proxy': self.proxies,
            'token': self.tokens,
            'password': self.passwords
        }

    def put(self, des, obj):
        queue = self.queues[des]
        queue.put(obj)

    def get(self, des, obj):
        queue = self.queues[des]
        queue.get(obj)

    def populate_passwords(self):
        log = logging.getLogger('Populating Passwords')
        log.info("Running...")

        for password in self.user.get_new_attempts():
            self.put('password', password)

        log.info("Done Populating Passwords")

    def populate_proxies(self):

        found_proxies = []
        log = logging.getLogger('Populating Proxy Queue')
        log.info("Running...")

        for link in settings.PROXY_LINKS:
            log.info(f"Scraping Proxies at {link}")
            proxy_api = ProxyApi(link)

            for proxy in proxy_api.get_proxies():
                if proxy.ip not in found_proxies:
                    self.put('proxy', proxy)
                    found_proxies.append(proxy.ip)

        log.info(f"Scraping Extra Proxies at {settings.EXTRA_PROXY}")
        proxy_api = ProxyApi(settings.EXTRA_PROXY)

        for proxy in proxy_api.get_extra_proxies():
            if proxy.ip not in found_proxies:
                self.put('proxy', proxy)
                found_proxies.append(proxy.ip)

        log.info("Done Populating Proxy Queue")


class QueueManagerAsync(QueueManagerSync):

    def __init__(self, user):
        self.user = user

        self.proxies = asyncio.LifoQueue()
        self.tokens = asyncio.Queue()
        self.passwords = asyncio.Queue()

    def put(self, des, obj):
        queue = self.queues[des]
        queue.put_nowait(obj)

    def get(self, des, obj):
        queue = self.queues[des]
        queue.get_nowait(obj)

    async def populate_proxies(self):

        found_proxies = []
        log = logging.getLogger('Populating Proxy Queue')
        log.info("Running...")

        for link in settings.PROXY_LINKS:
            log.info(f"Scraping Proxies at {link}")
            proxy_api = ProxyApi(link)

            for proxy in proxy_api.get_proxies():
                if proxy.ip not in found_proxies:
                    self.put('proxy', proxy)
                    found_proxies.append(proxy.ip)

        log.info(f"Scraping Extra Proxies at {settings.EXTRA_PROXY}")
        proxy_api = ProxyApi(settings.EXTRA_PROXY)

        for proxy in proxy_api.get_extra_proxies():
            if proxy.ip not in found_proxies:
                self.put('proxy', proxy)
                found_proxies.append(proxy.ip)

        log.info("Done Populating Proxy Queue")

    async def populate_passwords(self):

        log = logging.getLogger('Populating Passwords')
        log.info("Running...")

        for password in self.user.get_new_attempts():
            self.put('password', password)

        log.info("Done Populating Passwords")


