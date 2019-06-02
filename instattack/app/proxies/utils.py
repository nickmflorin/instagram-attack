from bs4 import BeautifulSoup
import requests

from .models import Proxy


def scrape_proxies(limit=None):
    """
    Not currently used, but could be useful.
    """
    url = "https://www.us-proxy.org/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')

    proxies = []
    table = soup.find_all('table', {'id': 'proxylisttable'})[0]
    rows = table.findChildren('tr')[1:]

    for row in rows:
        if limit and len(proxies) == limit:
            break

        children = row.findChildren('td')
        try:
            host = children[0].text
            port = children[1].text
            is_https = children[6].text
        except IndexError:
            break
        else:
            # We only want HTTP proxies.
            if is_https == 'no':
                proxy = Proxy(
                    host=host,
                    port=port,
                    avg_resp_time=0.1,  # Guess for now?
                )
                proxies.append(proxy)
    return proxies
