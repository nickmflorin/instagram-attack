from __future__ import absolute_import

from bs4 import BeautifulSoup
import random
import requests

import app.exceptions as exceptions
import app.settings as settings
from app.lib.models import InstagramResult, Proxy


__all__ = ('ProxyApi', 'InstagramApi', )


def ensure_safe_http(func):
    def wrapper(instance, *args, **kwargs):
        if not instance.proxies:
            raise exceptions.MissingProxyException()
        return func(instance, *args, **kwargs)
    return wrapper


# def set_token(func):
#     def wrapper(instance, *args, **kwargs):
#         if kwargs.get('token'):
#             instance.update_token(kwargs['token'])
#         return func(instance, *args, **kwargs)
#     return wrapper


# def ensure_token(func):
#     def wrapper(instance, *args, **kwargs):
#         if not instance.headers.get('x-csrftoken'):
#             raise exceptions.MissingTokenException()
#         return func(instance, *args, **kwargs)
#     return wrapper


class InstagramSession(requests.Session):

    __client_exception__ = exceptions.ApiClientException
    __server_exception__ = exceptions.ApiServerException

    __status_code_exceptions__ = {
        429: exceptions.ApiTooManyRequestsException
    }

    def __init__(self, proxy=None, token=None, *args, **kwargs):
        super(InstagramSession, self).__init__(*args, **kwargs)

        self.token = self.proxy = None

        self.headers = settings.HEADER.copy()
        self.headers['user-agent'] = random.choice(settings.USER_AGENTS)

        if token:
            self.update_token(token)
        if proxy:
            self.update_proxy(proxy)

    def update_proxy(self, proxy):
        self.proxy = proxy
        self.proxies.update(
            http=self.proxy.address,
            https=self.proxy.address
        )

    def update_token(self, token):
        self.token = token
        self.headers['x-csrftoken'] = self.token

    def _handle_response(self, response):
        try:
            response.raise_for_status()
        except requests.RequestException:
            if response.status_code >= 400 and response.status_code < 500:

                # Status Code 400 Refers to Checkpoint Required
                result = InstagramResult.from_response(response, expect_valid_json=False)
                if result:
                    if result.has_error:
                        result.raise_client_exception(status_code=response.status_code)
                        return result
                    # Error is still raised if message="checkpoint_required", but that
                    # means the password was correct.
                    elif result.accessed:
                        return result
                    else:
                        # If we hit this point, that means that the API response
                        # had content and we are not associating the error correctly.
                        raise exceptions.ApiException(
                            message="The result should have an error "
                            "if capable of being converted to JSON at this point."
                        )

                exc = self.__status_code_exceptions__.get(
                    response.status_code,
                    exceptions.ApiClientException
                )
                raise exc(status_code=response.status_code)
            else:
                raise self.__server_exception__(
                    status_code=response.status_code
                )
        else:
            result = InstagramResult.from_response(response)
            if result.has_error:
                result.raise_client_exception(status_code=400)
            return result

    def _handle_request_error(self, e, method, endpoint):
        error_kwargs = {
            'method': method,
            'endpoint': endpoint,
            'proxy': self.proxy
        }

        if isinstance(e, requests.exceptions.ProxyError):
            raise exceptions.ApiBadProxyException(**error_kwargs)
        elif isinstance(e, requests.exceptions.ConnectTimeout):
            raise exceptions.ApiTimeoutException(**error_kwargs)
        elif isinstance(e, requests.exceptions.ReadTimeout):
            raise exceptions.ApiTimeoutException(**error_kwargs)
        elif isinstance(e, requests.exceptions.SSLError):
            raise exceptions.ApiSSLException(**error_kwargs)
        elif isinstance(e, requests.exceptions.ConnectionError):
            # We can make a more appropriate exception later.
            raise exceptions.ApiBadProxyException(**error_kwargs)
        else:
            raise e

    @ensure_safe_http
    def get_token(self):
        try:
            response = super(InstagramSession, self).get(
                settings.INSTAGRAM_URL,
                timeout=settings.TOKEN_FETCH_TIME
            )
        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, 'GET', settings.INSTAGRAM_URL)
        else:
            cookies = response.cookies.get_dict()
            if 'csrftoken' not in cookies:
                raise exceptions.ApiBadProxyException(proxy=self.proxy)
            return cookies['csrftoken']

    # @set_token
    # @ensure_token
    @ensure_safe_http
    def post(self, endpoint, fetch_time=None, token=None, **data):
        fetch_time = fetch_time or settings.FETCH_TIME

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

    # @set_token
    @ensure_safe_http
    def get(self, endpoint, fetch_time=None, token=None, **data):
        fetch_time = fetch_time or settings.FETCH_TIME

        try:
            response = super(InstagramSession, self).get(
                endpoint,
                data=data,
                timeout=fetch_time
            )
        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, 'GET', endpoint)
        else:
            return self._handle_response(response)


class ProxyApi(object):

    __client_exception__ = exceptions.ApiClientException
    __server_exception__ = exceptions.ApiServerException

    def __init__(self, link):
        self.link = link

    def post(self, endpoint, **data):
        resp = self.session.post(endpoint, data=data, timeout=settings.FETCH_TIME)
        return self._handle_response(resp)

    def get(self, endpoint, **data):
        resp = requests.get(endpoint, data=data, timeout=settings.FETCH_TIME)
        return self._handle_response(resp)

    @classmethod
    def handle_response(cls, response, *args, **kwargs):
        return cls(*args, **kwargs)._handle_response(response)

    def _handle_response(self, response):
        try:
            response.raise_for_status()
        except requests.RequestException:
            if response.status_code >= 400 and response.status_code < 500:
                raise self.__client_exception__(response.status_code)
            else:
                raise self.__server_exception__(response.status_code)
        else:
            return response

    def get_proxies(self):
        response = self.get(self.link)
        body = BeautifulSoup(response.text, 'html.parser')

        table_rows = body.find('tbody').find_all('tr')
        for row in table_rows:
            proxy = Proxy.from_scraped_tr(row)
            if proxy:
                yield proxy

    def get_extra_proxies(self):
        response = self.get(settings.EXTRA_PROXY)

        def filter_ip_address(line):
            if line.strip() != "":
                if '-H' in line or '-S' in line:
                    if len(line.strip()) < 30:
                        return True
            return False

        body = BeautifulSoup(response.text, 'html.parser')
        lines = [line.strip() for line in body.string.split("\n")]
        ip_addresses = filter(filter_ip_address, lines)

        for proxy_string in ip_addresses:
            yield Proxy.from_text_file(proxy_string)


class InstagramApi(object):

    def __init__(self, username, proxy=None, token=None):
        self.username = username
        self.session = InstagramSession(
            proxy=proxy,
            token=token
        )

    def update_proxy(self, proxy):
        self.session.update_proxy(proxy)

    def update_token(self, token):
        self.session.update_token(token)

    def fetch_token(self, session, proxy):
        session.update_proxy(proxy)
        token = session.get_token()
        print(f"Token {token}")
        return token

    def login(self, password, token=None):
        print(f"Logging in with {password}.")

        data = {
            settings.INSTAGRAM_USERNAME_FIELD: self.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }
        return self.session.post(
            settings.INSTAGRAM_LOGIN_URL,
            token=token,
            **data
        )
