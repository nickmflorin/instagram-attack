from __future__ import absolute_import

import asyncio
import queue

from app import settings
from app.lib.api import ProxyApi
from app.lib.utils import auto_logger


__all__ = ('QueueManagerSync', 'QueueManagerAsync', )


class QueueManager(object):

    __loggers__ = {
        'populate_proxies': 'Populating Proxy Queue',
        'populate_passwords': 'Populating Passwords',
    }

    def __init__(self, user):
        self.user = user

        self.proxies = self.__queues_cls__['proxies']()
        self.tokens = self.__queues_cls__['tokens']()
        self.passwords = self.__queues_cls__['passwords']()
        self.attempts = self.__queues_cls__['attempts']()

    @property
    def queues(self):
        return {
            'proxy': self.proxies,
            'token': self.tokens,
            'password': self.passwords,
            'attempt': self.attempts
        }


class QueueManagerSync(QueueManager):

    __queues_cls__ = {
        'proxies': queue.LifoQueue,
        'tokens': queue.Queue,
        'passwords': queue.Queue,
        'attempts': queue.Queue,
    }

    def put(self, des, obj):
        queue = self.queues[des]
        queue.put(obj)

    def get(self, des):
        queue = self.queues[des]
        return queue.get()

    @auto_logger
    def populate_passwords(self, log):
        count = 1
        for password in self.user.get_new_attempts():
            count += 1
            self.put('password', password)

        if self.queues['password'].empty():
            log.exit("No new passwords to try.")
        log.info(f"Populated {count} Passwords")

    @auto_logger
    def populate_proxies(self, log):
        found_proxies = []

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

        log.info(f"Populated {len(found_proxies)} Proxies")


class QueueManagerAsync(QueueManager):

    __queues_cls__ = {
        'proxies': asyncio.LifoQueue,
        'tokens': asyncio.Queue,
        'passwords': asyncio.Queue,
        'attempts': asyncio.Queue,
    }

    def put(self, des, obj):
        queue = self.queues[des]
        queue.put_nowait(obj)

    def get(self, des):
        queue = self.queues[des]
        return queue.get_nowait()

    @auto_logger
    async def populate_proxies(self, log):

        found_proxies = []
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

        log.info(f"Populated {len(found_proxies)} Proxies")

    @auto_logger
    async def populate_passwords(self, log):
        count = 1
        for password in self.user.get_new_attempts():
            count += 1
            self.put('password', password)

        if self.queues['password'].empty():
            log.exit("No new passwords to try.")
        log.info(f"Populated {count} Passwords")
