from bs4 import BeautifulSoup
import requests
import json

from instattack.lib import logger
from instattack.lib.utils import start_and_stop


log = logger.get(__name__)


class ProxyScrape(object):

    def __init__(self, limit=None):
        self.limit = limit
        self.proxies = []

    def __call__(self):
        # with start_and_stop(f"Scraping Proxies from {self.url}"):
        r = requests.get(self.url)
        soup = BeautifulSoup(r.text, 'html.parser')
        self.eat_soup(soup)
        return self.proxies

    def add(self, host=None, port=None):
        log.debug('Host : %s' % host)
        self.proxies.append({
            'host': host,
            'port': port
        })

    def eat_rows(self, rows):
        row_index = 0
        while not self.stop and row_index < len(rows):
            self.eat_row(rows[row_index])
            row_index += 1

    @property
    def stop(self):
        if self.limit and len(self.proxies) == self.limit:
            return True
        return False


class GatherProxyOrg(ProxyScrape):
    """
    There seems to be some weird table population with Javascript that prevents
    us from seeing the raw HTML, but we can still parse the Javascript that is
    populating the cells of the table.

    This is a very good proxy list because it has additional helpful information
    and also is updated very frequently.

    There is additional information in each dict of the Javascript call, the
    available fields are:
    (1) PROXY_COUNTRY
    (2) PROXY_IP
    (3) PROXY_LAST_UPDATE
    (4) PROXY_PORT (In Hex)
    (5) PROXY_STATUS
    (6) PROXY_TIME
    (7) PROXY_TYPE (Elite, Transparent, Anonymous)
    (8) PROXY_UPTIMELD
    """
    url = "http://www.gatherproxy.com/"

    def eat_soup(self, soup):
        table = soup.find_all('table', {'id': 'tblproxy'})[0]
        scripts = table.find_all('script')
        self.eat_rows(scripts)

    def eat_row(self, row):
        if self.limit and len(self.proxies) == self.limit:
            return None

        text = row.text.strip()
        text = text.split('gp.insertPrx(')[1][:-2]
        data = json.loads(text)

        if data['PROXY_STATUS'] == 'OK':
            self.add(
                host=str(data['PROXY_IP']),
                port=int(data['PROXY_PORT'], 16)
            )
        else:
            log.warning('Discarding Scraped Proxy', extra={
                'other': 'Status: %s' % data['PROXY_STATUS']
            })


class USProxyOrg(ProxyScrape):
    """
    This proxy list seems to stay very constant.
    """
    url = "https://www.us-proxy.org/"

    def eat_soup(self, soup):
        table = soup.find_all('table', {'id': 'proxylisttable'})[0]
        rows = table.findChildren('tr')[1:]
        self.eat_rows(rows)

    def eat_row(self, row):
        if self.limit and len(self.proxies) == self.limit:
            return None

        children = row.findChildren('td')
        try:
            host = children[0].text
            port = children[1].text
            is_https = children[6].text
        except IndexError:
            pass
        else:
            # We only want HTTP proxies.
            if is_https == 'no':
                self.add(host=host, port=port)
