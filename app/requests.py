from __future__ import absolute_import

import collections
import contextlib
import random

import aiohttp
import asyncio
import concurrent.futures
import requests

from app import settings
from app.lib import exceptions
from app.lib.utils import auto_logger, format_proxy, get_token_from_response
from app.lib.models import InstagramResult

from app.handlers import AysncExceptionHandler, SyncExceptionHandler


"""
TODO
-----
Introduce timeout here if we cannot retrieve the token - if there is a connection
error we might not retrieve a token for any of the proxies.

We might want to try to refresh proxies after they are retrieved from
the queue if the request is successful.

NOTES
------
We can use the following url to make sure that requests are using the proxy
correctly:
future = session.get('https://api.ipify.org?format=json')
"""


TokenTaskContext = collections.namedtuple('TokenTaskContext',
    'name proxy session')
LoginTaskContext = collections.namedtuple('LoginTaskContext',
    'name proxy token session')


class request_handler(object):

    # Not currently being used but keep for now
    __client_exception__ = exceptions.InstagramClientApiException
    __server_exception__ = exceptions.InstagramServerApiException

    # Not currently being used but keep for now
    __status_code_exceptions__ = {
        429: exceptions.TooManyRequestsException,
        403: exceptions.ForbiddenException,
    }

    def __init__(self, global_stop_event, queues):
        self.global_stop_event = global_stop_event
        self.silenced = False
        self.user_agent = random.choice(settings.USER_AGENTS)
        self.stop_event = asyncio.Event()
        self.queues = queues

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @contextlib.asynccontextmanager
    async def silence(self):
        try:
            self.silenced = True
            yield
        finally:
            self.silenced = False


class token_handler(request_handler):

    # We are going to have to adjust these probably - it might take more than
    # 10 attempts to retrieve a result if we have bad proxies.
    ATTEMPT_LIMIT = settings.TOKEN_ATTEMPT_LIMIT
    THREAD_LIMIT = settings.TOKEN_THREAD_LIMIT

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    def _handle_client_response(self, response, log, extra=None):
        extra = extra or {}
        extra.update(response=response)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            log.warning(str(e), extra=extra)
            return None
        else:
            try:
                token = self._get_token_from_response(response)
            except exceptions.TokenNotInResponse as e:
                if not self.silenced:
                    log.warning(str(e), extra=extra)
                return None
            else:
                return token

    @auto_logger("Token Task")
    def request(self, session, proxy, task_name, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        extra = {
            'task': task_name,
            'proxy': proxy,
            'url': settings.INSTAGRAM_URL
        }

        if not self.silenced:
            log.info('Sending GET Request', extra=extra)
        try:
            response = session.get(
                settings.INSTAGRAM_URL,
                headers=self._headers(),
                timeout=settings.DEFAULT_TOKEN_FETCH_TIME,
                proxies={
                    'http': format_proxy(proxy),
                    'https': format_proxy(proxy, scheme='https'),
                }
            )
        except requests.exceptions.ConnectionError as e:
            if not self.silenced:
                log.error(str(e), extra=extra)
            return None
        else:
            token = self._handle_client_response(response, log, extra=extra)
            if token:
                self.queues.proxies.good.put_nowait(proxy)
            return token

    async def task_generator(self, log, **context):
        index = 0
        while not self.stop_event.is_set() and index <= self.ATTEMPT_LIMIT:
            proxy = await self.queues.proxies.get_best()
            index += 1

            _context = TokenTaskContext(
                name=f'Token Task {index}',
                proxy=proxy,
                **context,
            )

            log.debug("Submitting Task", extra={
                'task': _context.name,
            })

            yield _context

    @auto_logger("Getting Token")
    async def __call__(self, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        futures = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
            session = requests.Session()

            async for context in self.task_generator(log, session=session):
                log.debug("Submitting Task", extra={
                    'task': context.name
                })
                token_future = executor.submit(
                    self.request, context.session, context.proxy, context.name)

                setattr(token_future, '__context__', context)
                futures.append(token_future)

            for future in concurrent.futures.as_completed(futures):
                log.debug("Finished Task", extra={
                    'task': future.__context__.name,
                    'proxy': future.__context__.proxy,
                })
                result = future.result()
                if result is not None:
                    async with self.silence():
                        self.stop_event.set()
                        executor.shutdown()
                    return result


class login_handler(request_handler):

    # We are going to have to adjust these probably - it might take more than
    # 10 attempts to retrieve a result if we have bad proxies.
    ATTEMPT_LIMIT = settings.LOGIN_ATTEMPT_LIMIT
    THREAD_LIMIT = settings.LOGIN_THREAD_LIMIT

    def __init__(self, user, global_stop_event, queues):
        super(login_handler, self).__init__(global_stop_event, queues)
        self.user = user

    @property
    def login_data(self):
        return {
            'username': self.user.username,
            'password': self.user.password,
        }

    def _headers(self, token):
        headers = super(login_handler, self)._headers()
        headers['x-csrftoken'] = token
        return headers


class async_login_handler(login_handler):
    """
    Intention was to use asyncio with aiohttp sessions but aiohttp sessions
    have not been playing well with the token authentication - so this is in
    progress and TBD if we will use.
    """

    def _handle_client_response(self, response, log, extra=None):
        """
        Has to be rewritten for aiohttp case.
        """
        pass

    @auto_logger("Login")
    def request(self, session, proxy, token, task_name, log):
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
        extra = {
            'task': task_name,
            'proxy': proxy,
            'url': settings.INSTAGRAM_LOGIN_URL,
            'token': token,
        }

        if not self.silenced:
            log.info("Sending POST Request", extra=extra)

        log.info("Sending POST Request", extra={
            'url': settings.INSTAGRAM_LOGIN_URL,
            'proxy': proxy,
            'token': token,
        })

        try:
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                proxy=format_proxy(proxy),
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                headers=self._headers(token),
                json=self.login_data,
            ) as response:
                # TODO: For client responses, we might want to raise a harder exception
                # if we get a 403.
                return self._handle_client_response(response, log, extra=extra)

        except aiohttp.ClientError as exc:
            log.error(str(exc), extra={
                'proxy': proxy,
                'token': token,
            })

        try:
            response = session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(token),
                data=self.login_data,
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                proxies={
                    'http': format_proxy(proxy),
                    'https': format_proxy(proxy, scheme='https'),
                },
            )
        except aiohttp.exceptions.ConnectionError as e:
            if not self.silenced:
                log.error(str(e), extra=extra)
            return None
        else:
            # TODO: For client responses, we might want to raise a harder exception
            # if we get a 403.
            return self._handle_client_response(response, log, extra=extra)

    @auto_logger("Attempting Login")
    async def __call__(self, token, log):
        """
        Currently not working - needs work.
        """
        futures = []
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(headers=self._headers(token),
                connector=connector) as session:

            async for context in self.task_generator(log, session=session, token=token):
                login_future = asyncio.ensure_future(self.request(
                    context.session, context.proxy, context.token, context.name))
                setattr(login_future, '__context__', context)

                futures.append(login_future)

            # For conccurrent.futures case, we use `as_completed` - not sure if
            # there is an analogue, but these results need to be filtered
            # since they will be the raw results (possibly with exceptions -
            # but those should all be caught).
            results = await asyncio.gather(*futures)
            for future in results:
                # We are going to have to distinguish between accessed and not
                # accessed when there are generic type errors, but either one means
                # that we should be returning the result.
                result = future.result()
                if result and result.accessed:
                    async with self.silence():
                        self.stop_event.set()

                    self.queues.proxies.good.put_nowait(future.__context__.proxy)
                    return result


class futures_login_handler(login_handler):

    def _get_result_from_response(self, response):
        try:
            result = response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result)

    def _handle_client_response(self, response, log, extra=None):
        extra = extra or {}
        extra.update(response=response)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                try:
                    result = self._get_result_from_response(response)
                except exceptions.ResultNotInResponse:
                    log.warning(str(e), extra=extra)
                    return None
                else:
                    return result
            else:
                log.warning(str(e), extra=extra)
                return None
        else:
            try:
                result = self._get_result_from_response(response)
            except exceptions.ResultNotInResponse:
                log.critical("Unexpected behavior, result should be in response.")
                return None
            else:
                return result

    @auto_logger("Login")
    def request(self, session, proxy, token, task_name, log):

        extra = {
            'task': task_name,
            'proxy': proxy,
            'url': settings.INSTAGRAM_LOGIN_URL,
            'token': token,
        }

        if not self.silenced:
            log.info("Sending POST Request", extra=extra)
        try:
            response = session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(token),
                data=self.login_data,
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                proxies={
                    'http': format_proxy(proxy),
                    'https': format_proxy(proxy, scheme='https'),
                },
            )
        except requests.exceptions.ConnectionError as e:
            if not self.silenced:
                log.error(str(e), extra=extra)
            return None
        else:
            # TODO: For client responses, we might want to raise a harder exception
            # if we get a 403.
            return self._handle_client_response(response, log, extra=extra)

    async def task_generator(self, log, **context):
        index = 0
        while not self.stop_event.is_set() and index <= self.ATTEMPT_LIMIT:
            proxy = await self.queues.proxies.get_best()
            index += 1

            _context = LoginTaskContext(
                name=f'Login Task {index}',
                proxy=proxy,
                **context,
            )

            log.debug("Submitting Task", extra={
                'task': _context.name,
            })

            yield _context

    @auto_logger("Attempting Sync Login")
    async def sync(self, token, log):

        session = requests.Session()
        async for context in self.task_generator(log, session=session, token=token):
            result = self.request(
                context.session, context.proxy, context.token, context.name)
            if result and result.accessed:
                self.queues.proxies.good.put_nowait(context.proxy)

                self.stop_event.set()
                return result

    @auto_logger("Attempting Login")
    async def __call__(self, token, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        futures = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
            session = requests.Session()

            async for context in self.task_generator(log, session=session, token=token):

                login_future = executor.submit(
                    self.request, context.session, context.proxy, context.token, context.name)
                setattr(login_future, '__context__', context)

                futures.append(login_future)

            for future in concurrent.futures.as_completed(futures):
                log.debug("Finished Task", extra={
                    'task': future.__context__.name,
                    'proxy': future.__context__.proxy,
                })
                result = future.result()
                # We are going to have to distinguish between accessed and not
                # accessed when there are generic type errors, but either one means
                # that we should be returning the result.
                if result and result.accessed:
                    async with self.silence():
                        self.stop_event.set()
                        executor.shutdown()

                    self.queues.proxies.good.put_nowait(future.__context__.proxy)
                    return result


class Login(object):

    def __init__(self, user, global_stop_event, queues, config):

        self.futures_login_handler = futures_login_handler(user, global_stop_event, queues)
        self.token_handler = token_handler(global_stop_event, queues)
        self.global_stop_event = global_stop_event
        self.queues = queues
        self.config = config


class FuturesLogin(Login):

    @auto_logger("Login")
    async def login(self, loop, log):
        token = await self.token_handler()
        log.success("Set Token", extra={'token': token})

        if self.config.sync:
            result = await self.futures_login_handler.sync(token)
        else:
            result = await self.futures_login_handler(token)

        log.success('Got Login Result')
        log.success(result)
        self.global_stop_event.set()
