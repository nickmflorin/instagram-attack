from __future__ import absolute_import

import aiohttp
import asyncio

from bs4 import BeautifulSoup
import logging
import random

from app import settings
from app.lib import exceptions
from app.lib.logging import AppLogger
from app.lib.models import Proxy


__all__ = ('InstagramSession', 'ProxySession', )


class CustomAioSession(aiohttp.ClientSession):

    __status_code_exceptions__ = {
        429: exceptions.TooManyRequestsException,
        403: exceptions.ForbiddenException,
    }

    def __init__(self, **kwargs):
        kwargs['connector'] = aiohttp.TCPConnector(verify_ssl=False)
        kwargs['headers'] = settings.HEADER.copy()
        kwargs['headers']['user-agent'] = random.choice(settings.USER_AGENTS)
        super(CustomAioSession, self).__init__(**kwargs)

        logging.setLoggerClass(AppLogger)
        self.log = logging.getLogger(self.__class__.__name__)

    async def _handle_response(self, response, proxy=None):
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
                    proxy=proxy,
                    status_code=response.status
                )
            else:
                raise exceptions.ServerResponseException(
                    proxy=proxy,
                    message=response.reason,
                    status_code=response.status
                )
        else:
            return response


class ProxySession(CustomAioSession):

    __client_exception__ = exceptions.ClientApiException
    __server_exception__ = exceptions.ServerApiException

    async def get_proxies(self, link):
        proxy_list = []
        async with self.get(link, timeout=settings.DEFAULT_FETCH_TIME) as response:

            response = await self._handle_response(response)
            self.log.success(f"Received Response", extra={'response': response})

            response_text = await response.text()
            body = BeautifulSoup(response_text, 'html.parser')
            table_rows = body.find('tbody').find_all('tr')

            for row in table_rows:
                proxy = Proxy.from_scraped_tr(row)

                if proxy and proxy not in proxy_list:
                    proxy_list.append(proxy)
        return proxy_list

    async def get_extra_proxies(self):
        proxy_list = []
        async with self.get(settings.EXTRA_PROXY,
                timeout=settings.DEFAULT_FETCH_TIME) as response:

            response = await self._handle_response(response)
            self.log.success(f"Received Response", extra={'response': response})

            def filter_ip_address(line):
                if line.strip() != "":
                    if '-H' in line or '-S' in line:
                        if len(line.strip()) < 30:
                            return True
                return False

            response_text = await response.text()

            body = BeautifulSoup(response_text, 'html.parser')
            lines = [line.strip() for line in body.string.split("\n")]
            ip_addresses = filter(filter_ip_address, lines)

            for proxy_string in ip_addresses:
                proxy_list.append(Proxy.from_text_file(proxy_string))
        return proxy_list


class InstagramSession(CustomAioSession):

    __client_exception__ = exceptions.InstagramClientApiException
    __server_exception__ = exceptions.InstagramServerApiException

    async def _handle_login_response(self, response, proxy):
        return await self._handle_response(response, proxy)
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

    def _handle_client_error(self, e, proxy):
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
            raise exceptions.ServerTimeoutError(e.message, proxy=proxy)

        # ClientOSError does not have message attribute.
        elif isinstance(e, aiohttp.ClientOSError):
            raise exceptions.ClientOSError(str(e), proxy=proxy)

        elif isinstance(e, asyncio.TimeoutError):
            raise exceptions.ServerTimeoutError(e.message, proxy=proxy)

        elif isinstance(e, aiohttp.ServerDisconnectedError):
            raise exceptions.ServerDisconnectedError(e.message, proxy=proxy)

        elif isinstance(e, aiohttp.ClientHttpProxyError):
            raise exceptions.ClientHttpProxyError(e.message, proxy=proxy)

        elif isinstance(e, aiohttp.ClientProxyConnectionError):
            raise exceptions.ClientProxyConnectionError(e.message, proxy=proxy)
        else:
            raise e

    async def prepare_for_request(self, **kwargs):
        if 'token' in kwargs:
            self._default_headers.update({'x-csrftoken': kwargs['token']})

    async def get_base_response(self, proxy, as_token=False, as_cookies=False):
        await self.prepare_for_request()
        try:
            async with await self.get(
                settings.INSTAGRAM_URL,
                proxy=proxy.url(),
                timeout=settings.DEFAULT_TOKEN_FETCH_TIME
            ) as response:
                response = await self._handle_response(response, proxy=proxy)
                return (proxy, response)

        except aiohttp.ClientError as exc:
            self._handle_client_error(exc, proxy)

    async def login(self, username, password, token, proxy, as_response=False):
        await self.prepare_for_request(token=token)
        data = {
            'username': username,
            'password': password,
        }
        try:
            async with self.post(
                settings.INSTAGRAM_LOGIN_URL,
                proxy=proxy.url(),
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                json=data,
            ) as response:
                return await self._handle_login_response(response, proxy)
        except aiohttp.ClientError as exc:
            self._handle_client_error(exc, proxy=proxy)
