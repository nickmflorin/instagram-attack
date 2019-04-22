from __future__ import absolute_import

import subprocess
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


def get_pids_from_terminal_content(content, port, limit=None):
    lines = content.split('\n')
    if len(lines) < 2:
        raise IOError(f"Invalid content returned from lsof -i:{port}")

    lines = lines[1:]
    if limit:
        lines = lines[:limit]

    rows = [
        [item for item in line.split(' ') if item.strip() != '']
        for line in lines
    ]

    if limit == 1:
        return int(rows[0][1])

    pids = []
    for row in rows:
        try:
            pids.append(row[1])
        except IndexError:
            continue
    return [int(pid) for pid in pids]


def find_pids_on_port(port):
    try:
        content = subprocess.check_output(['lsof', '-i', ':%s' % port], universal_newlines=True)
    except subprocess.CalledProcessError:
        return []
    else:
        pids = get_pids_from_terminal_content(content, port)
        return list(set(pids))
