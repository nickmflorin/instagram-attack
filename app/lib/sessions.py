from __future__ import absolute_import

import random
import requests

from app import settings

from app.lib import exceptions
from app.lib.models import InstagramResult
from app.lib.utils import ensure_safe_http, update_proxy_if_provided


__all__ = ('InstagramSession', )


class InstagramSession(requests.Session):

    __client_exception__ = exceptions.ApiClientException
    __server_exception__ = exceptions.ApiServerException

    __status_code_exceptions__ = {
        429: exceptions.ApiTooManyRequestsException
    }

    def __init__(self, user, proxy=None, *args, **kwargs):
        super(InstagramSession, self).__init__(*args, **kwargs)

        self.user = user
        self.token = self.proxy = None

        self.headers = settings.HEADER.copy()
        self.headers['user-agent'] = random.choice(settings.USER_AGENTS)

        if proxy:
            self.update_proxy(proxy)

    def update_proxy(self, proxy):
        self.proxy = proxy
        self.proxies.update(
            http=self.proxy.address,
            https=self.proxy.address
        )

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

    @ensure_safe_http
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

    @ensure_safe_http
    @update_proxy_if_provided
    def get(self, endpoint, fetch_time=None, proxy=None, **data):
        fetch_time = fetch_time or settings.DEFAULT_FETCH_TIME

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

    @update_proxy_if_provided
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
