from __future__ import absolute_import

import aiohttp
import asyncio
from bs4 import BeautifulSoup
import logging
import random
import requests

from app import settings
from app.lib import exceptions
from app.lib.logging import SessionLogger
from app.lib.models import InstagramResult, Proxy


__all__ = ('InstagramSession', 'ProxySession', )


class CustomAioSession(aiohttp.ClientSession):

    def __init__(self):
        super(CustomAioSession, self).__init__(
            connector=aiohttp.TCPConnector(verify_ssl=False)
        )

        logging.setLoggerClass(SessionLogger)
        self.log = logging.getLogger(self.__class__.__name__)

    def _handle_response(self, response):
        try:
            response.raise_for_status()
        except requests.RequestException:
            if response.status_code >= 400 and response.status_code < 500:
                raise exceptions.ApiClientException(response.status_code)
            else:
                raise exceptions.ApiServerException(response.status_code)
        else:
            return response


class ProxySession(CustomAioSession):

    async def get_proxies(self, link):
        proxy_list = []
        async with self.get(link, timeout=settings.DEFAULT_FETCH_TIME) as response:

            response = self._handle_response(response)
            self.log.success(f"Received Response", extra={
                'url': link,
                'status_code': response.status,
            })

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

            response = self._handle_response(response)

            self.log.success(f"Received Response", extra={
                'url': settings.EXTRA_PROXY,
                'status_code': response.status,
            })

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

    __status_code_exceptions__ = {
        429: exceptions.TooManyRequestsException
    }

    def _handle_login_response(self, response):
        result = InstagramResult.from_response(response)
        if not result:
            return self._handle_response(response)

        if result.has_error:
            result.raise_client_exception(status_code=response.status_code)
        elif result.accessed:
            # Error is still raised if message="checkpoint_required", but that
            # means the password was correct.
            return result
        else:
            # If we hit this point, that means that the API response
            # had content and we are not associating the error correctly.
            raise exceptions.ApiException(
                message="The result should have an error "
                "if capable of being converted to JSON at this point."
            )

    def _handle_response(self, response):
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError:
            if response.status_code >= 400 and response.status_code < 500:
                exc = self.__status_code_exceptions__.get(
                    response.status_code,
                    exceptions.ClientResponseException
                )
                raise exc(status_code=response.status_code)
            else:
                raise exceptions.ServerResponseException(
                    message=response.reason,
                    status_code=response.status_code
                )
        else:
            return response

    def _handle_request_error(self, e, **details):
        """
        TimeoutError is more general form of ServerTimeoutError, which exists
        for asyncio but not aiohttp, so for now we will treat them the same until
        the difference is determined.
        """
        if isinstance(e, aiohttp.ClientConnectorError):
            raise exceptions.RequestsConnectionException(**details)
        elif isinstance(e, aiohttp.ServerTimeoutError):
            raise exceptions.RequestsTimeoutException(**details)
        elif isinstance(e, asyncio.TimeoutError):
            raise exceptions.RequestsTimeoutException(**details)
        elif isinstance(e, aiohttp.ClientOSError):
            raise exceptions.RequestsOSError(**details)
        elif isinstance(e, aiohttp.ServerDisconnectedError):
            raise exceptions.RequestsDisconnectError(**details)
        elif isinstance(e, aiohttp.ClientHttpProxyError):
            raise exceptions.ClientHttpProxyException(**details)
        else:
            raise e

    async def get_token(self, proxy):

        self.headers = settings.HEADER.copy()
        self.headers['user-agent'] = random.choice(settings.USER_AGENTS)

        self.log.info(f"Fetching Token with {proxy.ip}")
        try:
            async with self.get(
                settings.INSTAGRAM_URL,
                proxy=proxy.url(),
                timeout=settings.DEFAULT_TOKEN_FETCH_TIME
            ) as response:
                response = self._handle_response(response)
                if not response.cookies.get('csrftoken'):
                    raise exceptions.TokenNotInResponse(proxy=proxy)

                return response.cookies['csrftoken'].value

        except Exception as exc:
            self._handle_request_error(exc, proxy=proxy)

    async def login(self, username, password, token, proxy):
        data = {
            settings.INSTAGRAM_USERNAME_FIELD: username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

        self.log.info(f"Logging in with {password} {proxy.ip}")

        self.headers = settings.HEADER.copy()
        self.headers['user-agent'] = random.choice(settings.USER_AGENTS)
        self.headers['x-csrftoken'] = token

        try:
            async with self.post(
                settings.INSTAGRAM_LOGIN_URL,
                proxy=proxy.url(),
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                **data
            ) as response:
                return self._handle_login_response(response)

        except Exception as exc:
            self._handle_request_error(exc, proxy=proxy)
