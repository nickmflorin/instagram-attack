from __future__ import absolute_import

from bs4 import BeautifulSoup as soup
from collections import namedtuple
import random
import requests
import urllib3

from app.exceptions import (ApiClientException, ApiServerException,
    InstagramClientException, InstagramServerException, InvalidUserName,
    BadProxyError)
import app.settings as settings


__all__ = ('ProxyApi', 'InstagramApi', )


Proxy = namedtuple('Proxy', ['ip', 'port', 'country'])


class InstagramSession(requests.Session):

    __client_exception__ = InstagramClientException
    __server_exception__ = InstagramServerException

    def __init__(self, proxy, *args, **kwargs):
        super(InstagramSession, self).__init__(*args, **kwargs)

        self.headers = settings.HEADER.copy()
        self.headers['user-agent'] = random.choice(settings.USER_AGENTS)
        self.set_proxy(proxy)

    def set_proxy(self, proxy):
        self.proxy = proxy

        addr = '{}:{}'.format(self.proxy.ip, self.proxy.port)
        self.proxies.update(
            http=addr,
            https=addr
        )

    def _handle_response(self, response):
        try:
            response.raise_for_status()
        except requests.RequestException:
            if response.status_code >= 400 and response.status_code < 500:
                raise self.__client_exception__(response)
            else:
                raise self.__server_exception__(response)
        else:
            return response

    def post(self, endpoint, **data):
        try:
            resp = super(InstagramSession, self).post(endpoint,
                data=data, timeout=settings.FETCH_TIME)
        except urllib3.exceptions.MaxRetryError:
            raise BadProxyError(self.proxy)
        else:
            return self._handle_response(resp)

    def get(self, endpoint, **data):
        return super(InstagramSession, self).get(endpoint, data=data,
            timeout=settings.FETCH_TIME)


class Api(object):

    def __init__(self):
        pass

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


class ProxyApi(Api):

    __client_exception__ = ApiClientException
    __server_exception__ = ApiServerException

    def __init__(self, link):
        self.link = link

    def _parse_extra_proxy(self, proxy):
        proxy = proxy.split(' ')
        addr = proxy[0].split(':')
        return Proxy(
            ip=addr[0],
            port=addr[1],
            country=addr[1].split('-')[0]
        )

    def _parse_proxy(self, proxy):
        proxy = proxy.find_all('td')
        if 'transparent' not in (proxy[4].string, proxy[5].string):
            return Proxy(
                ip=proxy[0].string,
                port=proxy[1].string,
                country=proxy[3].string
            )

    def get_proxies(self):
        response = self.get(self.link)
        body = soup(response.text, 'html.parser')

        proxies = body.find('tbody').find_all('tr')
        for proxy in proxies:
            if proxy:
                _proxy = self._parse_proxy(proxy)
                if _proxy:
                    yield _proxy

    def get_extra_proxies(self):
        # The previous code was built almost like it expected this to fail
        # occasionally, so we should too.
        response = self.get(settings.EXTRA_PROXY)
        for proxy in response:
            if '-H' in proxy and '-S' in proxy:
                yield self.parse_extra_proxy(proxy)


class InstagramApi(Api):

    def __init__(self, username, proxy):
        self.username = username
        self.proxy = proxy

        self.session = InstagramSession(self.proxy)
        self._token = None

    @property
    def token(self):
        if not self._token:
            self._token = self.refresh_token()
        return self._token

    def post(self, endpoint, **data):
        if 'token' not in self.session.headers:
            self.session.headers['x-csrftoken'] = self.token
        return self.session.post(endpoint, **data)

    def get(self, endpoint, **data):
        return self.session.get(endpoint, **data)

    def refresh_token(self):
        response = self.get(settings.INSTAGRAM_URL)
        cookies = response.cookies.get_dict()
        return cookies['csrftoken']

    def _format_state(self, results):
        state = {
            'accessed': False,
            'locked': False,
        }

        if 'user' not in results or not results['user']:
            raise InvalidUserName(self.username)

        if 'authenticated' in results:
            state['accessed'] = results['authenticated']

        elif 'message' in results and results['message'] == 'checkpoint_required':
            state['accesed'] = True

        elif 'status' in results and results['status'] == 'fail':
            state['locked'] = True

        return state

    def login(self, password):
        data = {
            settings.INSTAGRAM_USERNAME_FIELD: self.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }
        response = self.post(settings.INSTAGRAM_LOGIN_URL, **data)
        results = response.json()
        return self._format_state(results)
