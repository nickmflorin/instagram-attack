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
        async with self.get(link, timeout=settings.DEFAULT_AIO_FETCH_TIME) as response:

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
                timeout=settings.DEFAULT_AIO_FETCH_TIME) as response:

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

    # __status_code_exceptions__ = {
    #     429: exceptions.ApiTooManyRequestsException
    # }

    # def _handle_response(self, response):
    #     try:
    #         response.raise_for_status()
    #     except requests.RequestException:
    #         if response.status_code >= 400 and response.status_code < 500:

    #             # Status Code 400 Refers to Checkpoint Required
    #             result = InstagramResult.from_response(response, expect_valid_json=False)
    #             if result:
    #                 if result.has_error:
    #                     result.raise_client_exception(status_code=response.status_code)
    #                     return result
    #                 # Error is still raised if message="checkpoint_required", but that
    #                 # means the password was correct.
    #                 elif result.accessed:
    #                     return result
    #                 else:
    #                     # If we hit this point, that means that the API response
    #                     # had content and we are not associating the error correctly.
    #                     raise exceptions.ApiException(
    #                         message="The result should have an error "
    #                         "if capable of being converted to JSON at this point."
    #                     )

    #             exc = self.__status_code_exceptions__.get(
    #                 response.status_code,
    #                 exceptions.ApiClientException
    #             )
    #             raise exc(status_code=response.status_code)
    #         else:
    #             raise self.__server_exception__(
    #                 status_code=response.status_code
    #             )
    #     else:
    #         result = InstagramResult.from_response(response)
    #         if result.has_error:
    #             result.raise_client_exception(status_code=400)
    #         return result

    def _handle_response_error(self, e, details):
        if isinstance(e, aiohttp.ClientHttpProxyError):
            raise exceptions.ApiBadProxyException(**details)

    def _handle_request_error(self, e, details):
        # FOR NOW, just treat them all as bad proxies
        if isinstance(e, aiohttp.ClientConnectorError):
            raise exceptions.ApiBadProxyException(**details)
        elif isinstance(e, aiohttp.ServerTimeoutError):
            raise exceptions.ApiBadProxyException(**details)

        # TimeoutError is more general form of ServerTimeoutError, we should
        # probably just stick to that one since it does indicate slow connections
        # to proxies which slow down search.
        elif isinstance(e, asyncio.TimeoutError):
            raise exceptions.ApiBadProxyException(**details)

    def _handle_session_error(self, e, proxy, method, endpoint):
        details = {
            'method': method,
            'endpoint': endpoint,
            'proxy': proxy
        }
        self._handle_request_error(e, details=details)
        self._handle_response_error(e, details=details)
        raise e

    async def get_token(self, proxy):

        self.headers = settings.HEADER.copy()
        self.headers['user-agent'] = random.choice(settings.USER_AGENTS)

        self.log.info(f"Fetching Token with {proxy.ip}")
        try:
            async with self.get(settings.INSTAGRAM_URL,
                    proxy=proxy.url(),
                    timeout=settings.DEFAULT_AIO_FETCH_TIME) as response:

                return response.cookies
        except Exception as exc:
            self._handle_session_error(exc, proxy, 'GET', settings.INSTAGRAM_URL)
        # except requests.exceptions.RequestException as e:
        #     self._handle_request_error(e, 'GET', settings.INSTAGRAM_URL)
        # else:
        #     cookies = response.cookies.get_dict()
        #     if 'csrftoken' not in cookies:
        #         raise exceptions.ApiBadProxyException(proxy=self.proxy)
        #     return cookies['csrftoken']

    def post(self, endpoint, token, fetch_time=None, **data):
        fetch_time = fetch_time or settings.DEFAULT_FETCH_TIME
        self.headers['x-csrftoken'] = token

        try:
            response = super(InstagramSession, self).post(
                endpoint,
                data=data,
                timeout=fetch_time
            )
        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, 'POST', endpoint)
        else:
            return self._handle_response(response)

    def login(self, password, token, proxy=None):
        data = {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }
        return self.post(
            settings.INSTAGRAM_LOGIN_URL,
            token=token,
            fetch_time=settings.LOGIN_FETCH_TIME,
            **data
        )
