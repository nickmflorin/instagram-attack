from __future__ import absolute_import

import aiohttp
import asyncio

import logging
import random

from app import settings
from app.lib import exceptions
from app.lib.logging import AppLogger


__all__ = ('InstagramSession', )


class InstagramSession(aiohttp.ClientSession):

    __client_exception__ = exceptions.InstagramClientApiException
    __server_exception__ = exceptions.InstagramServerApiException

    __status_code_exceptions__ = {
        429: exceptions.TooManyRequestsException,
        403: exceptions.ForbiddenException,
    }

    def __init__(self, **kwargs):
        kwargs['connector'] = aiohttp.TCPConnector(ssl=False)
        kwargs['headers'] = settings.HEADER.copy()
        kwargs['headers']['user-agent'] = random.choice(settings.USER_AGENTS)
        super(InstagramSession, self).__init__(**kwargs)

        logging.setLoggerClass(AppLogger)
        self.log = logging.getLogger(self.__class__.__name__)

    async def _handle_response(self, response):
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError:
            if response.status >= 400 and response.status < 500:
                exc = self.__status_code_exceptions__.get(
                    response.status,
                    self.__client_exception__,
                )
                raise exc(
                    response.reason,
                    status_code=response.status
                )
            else:
                raise exceptions.ServerResponseException(
                    message=response.reason,
                    status_code=response.status
                )
        else:
            return response

    async def _handle_login_response(self, response):
        return await self._handle_response(response)
        # try:
        #     data = await response.read()
        # except aiohttp.ClientConnectionError:
        #     raise exceptions.BadProxyClientException(
        #         proxy=proxy,
        #         status_code=response.status,
        #         # Automate the combination of bad proxy and specific messages
        #         message="Client Connection Error - Bad Proxy",
        #     )
        # else:
        #     try:
        #         data = json.loads(data)
        #     except ValueError:
        #         return self._handle_response(response, proxy)
        #     else:
        #         result = InstagramResult.from_dict(**data)
        #         if result.has_error:
        #             raise exceptions.InstagramResponseException(result=result)
        #         elif not result.accessed:
        #             self.log.warn("Result did not have error but was not accessed.",
        #                 extra={'result': result})
        #         return response

    def _handle_client_error(self, e):
        """
        TimeoutError is more general form of ServerTimeoutError, which exists
        for asyncio but not aiohttp, so for now we will treat them the same until
        the difference is determined.

        TODO:
        This is not a good way to handle this, we should rely on the aiohttp
        exceptions more instead of ours and have the proxy passed in another
        way.
        """
        if isinstance(e, aiohttp.ServerTimeoutError):
            raise exceptions.ServerTimeoutError(e.message)

        # ClientOSError does not have message attribute.
        elif isinstance(e, aiohttp.ClientOSError):
            raise exceptions.ClientOSError(str(e))

        elif isinstance(e, asyncio.TimeoutError):
            raise exceptions.ServerTimeoutError(e.message)

        elif isinstance(e, aiohttp.ServerDisconnectedError):
            raise exceptions.ServerDisconnectedError(e.message)

        elif isinstance(e, aiohttp.ClientHttpProxyError):
            raise exceptions.ClientHttpProxyError(e.message)

        elif isinstance(e, aiohttp.ClientProxyConnectionError):
            raise exceptions.ClientProxyConnectionError(e.message)
        else:
            raise e

    async def prepare_for_request(self, **kwargs):
        if 'token' in kwargs:
            self._default_headers.update({'x-csrftoken': kwargs['token']})

    async def fetch(self, proxy):
        await self.prepare_for_request()
        try:
            async with await self.get(
                settings.INSTAGRAM_URL,
                proxy=f"http://{proxy.host}:{proxy.port}/",
                timeout=settings.DEFAULT_TOKEN_FETCH_TIME
            ) as response:
                try:
                    response = await self._handle_response(response)
                except exceptions.ApiException as e:
                    self.log.error(e.message, extra={
                        'proxy': proxy,
                        'response': response,
                    })
                else:
                    return response

        except aiohttp.ClientError as exc:
            self.log.error(exc.__class__.__name__, extra={
                'proxy': proxy,
            })
            return None
            # self._handle_client_error(exc, proxy)

    async def login(self, username, password, token, proxy):
        await self.prepare_for_request(token=token)
        data = {
            'username': username,
            'password': password,
        }

        async def try_login(data, token, proxy):
            try:
                self.log.info(f"http://{proxy.host}:{proxy.port}/")
                self.log.info(token)
                with self.post(
                    settings.INSTAGRAM_LOGIN_URL,
                    proxy=f"https://{proxy.host}:{proxy.port}/",
                    timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                    json=data,
                ) as response:
                    response = await self._handle_response(response)
                    import ipdb; ipdb.set_trace()
                    return await response.json()
                    # try:
                    #     response = await self._handle_response(response)
                    # except exceptions.ApiException as e:
                    #     self.log.error(e.message, extra={
                    #         'proxy': proxy,
                    #         'response': response,
                    #     })
                    # else:
                    #     return await response.json()

            except aiohttp.ClientError as exc:
                raise exc
                # self._handle_client_error(exc, proxy)
                # self.log.error(exc.__class__.__name__, extra={
                #     'proxy': proxy,
                # })
                # return None

        return await try_login(data, token, proxy)
