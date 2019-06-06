from bs4 import BeautifulSoup
import requests

from instattack.lib.utils import start_and_stop


class ProxyScrape(object):

    def __init__(self, limit=None):
        self.limit = limit
        self.proxies = []

    def __call__(self):
        with start_and_stop(f"Scraping Proxies from {self.url}"):
            r = requests.get(self.url)
            soup = BeautifulSoup(r.text, 'html.parser')
            self.eat_soup(soup)
            return self.proxies

    def add(self, host=None, port=None):
        print('Host : %s' % host)
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
    url = "http://http://www.gatherproxy.com//"

    def eat_soup(self, soup):
        table = soup.find_all('table', {'id': 'tblproxy'})[0]
        rows = table.findChildren('tr')[2:]
        self.eat_rows(rows)

    def eat_row(self, row):
        if self.limit and len(self.proxies) == self.limit:
            return None

        children = row.findChildren('td')
        try:
            host = children[1].text
            port = children[2].text
        except IndexError:
            pass
        else:
            self.add(host=host, port=port)


class USProxyOrg(ProxyScrape):
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


def scrape_proxies(limit=None):
    """
    Not currently used, but could be useful.
    """
    # scrape = USProxyOrg(limit=limit)
    scrape = GatherProxyOrg(limit=limit)
    scrape()
    return []
    # return scrape()
