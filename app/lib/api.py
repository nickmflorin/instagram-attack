from __future__ import absolute_import

from bs4 import BeautifulSoup
import requests

from app import settings
from app.lib import exceptions

from app.lib.models import Proxy


__all__ = ('ProxyApi', )


class ProxyApi(object):

    __client_exception__ = exceptions.ApiClientException
    __server_exception__ = exceptions.ApiServerException

    def __init__(self, link):
        self.link = link

    def post(self, endpoint, **data):
        resp = self.session.post(endpoint, data=data, timeout=settings.DEFAULT_FETCH_TIME)
        return self._handle_response(resp)

    def get(self, endpoint, **data):
        resp = requests.get(endpoint, data=data, timeout=settings.DEFAULT_FETCH_TIME)
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
