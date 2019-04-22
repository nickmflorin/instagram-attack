from __future__ import absolute_import

from app import settings
from app.lib.models import Proxy


def parse_proxy(line):
    pieces = line.strip().split(',')
    return Proxy(
        host=str(pieces[0].split(':')[0]),
        port=int(pieces[0].split(':')[1]),
        avg_resp_time=float(pieces[1]),
        error_rate=float(pieces[2]),
    )


def read_proxies(method="POST", limit=None, order_by=None):

    filename = "%s.txt" % settings.FILENAMES.PROXIES[method]

    proxies = []
    with open(filename, "r") as file:
        for line in file.readlines():
            if (not limit or len(proxies) <= limit):
                proxy = parse_proxy(line)
                proxies.append(proxy)
            else:
                break

    if order_by:
        proxies = sorted(proxies, key=lambda x: getattr(x, order_by))
    return proxies


def write_proxies(proxies, method='POST', overwrite=False):

    filename = "%s.txt" % settings.FILENAMES.PROXIES[method]

    add_proxies = proxies[:]
    if not overwrite:
        add_proxies = read_proxies(method=method)
        for proxy in proxies:
            if proxy not in add_proxies:
                add_proxies.append(proxy)

    with open(filename, "w+") as file:
        for proxy in add_proxies:
            file.write(
                f"{proxy.host}:{proxy.port},"
                f"{proxy.avg_resp_time},{proxy.error_rate}\n"
            )
