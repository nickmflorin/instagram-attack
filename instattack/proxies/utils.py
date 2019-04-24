from __future__ import absolute_import

import subprocess
from plumbum import local

from instattack.conf import settings
from instattack.conf.utils import validate_method

from instattack.logger import AppLogger

from .models import Proxy
from .exceptions import InvalidFileLine


log = AppLogger(__file__)


def parse_proxy(proxy):
    return (
        f"{proxy.host}:{proxy.port},"
        f"{proxy.avg_resp_time},{proxy.error_rate}\n"
    )


def reverse_parse_proxy(line):
    line = line.strip()

    # TODO: We probably shouldn't issue a warning if this is the case and just
    # silently ignore.
    if line == "":
        raise InvalidFileLine(line)

    if ',' not in line:
        raise InvalidFileLine(line)

    pieces = line.split(',')

    if len(pieces) != 3:
        raise InvalidFileLine(line)
    try:
        return Proxy(
            host=str(pieces[0].split(':')[0]),
            port=int(pieces[0].split(':')[1]),
            avg_resp_time=float(pieces[1]),
            error_rate=float(pieces[2]),
        )
    except (ValueError, IndexError, TypeError):
        raise InvalidFileLine(line)


def get_proxy_file_path(method):
    validate_method(method)
    filename = "%s.txt" % method.lower()
    return local.cwd / settings.APP_NAME / settings.PROXY_DIR / settings.DATA_DIR / filename


def read_proxies(method, limit=None, order_by=None):

    filepath = get_proxy_file_path(method)

    # This might actually happen when initially running app without files
    # (or if the user deletes it for whatever reason).
    if not filepath.exists():
        filepath.touch()

    if not filepath.is_file():
        raise FileNotFoundError('No such file: %s' % filepath)

    raw_data = filepath.read()
    raw_values = [val.strip() for val in raw_data.split('\n')]
    if limit:
        raw_values = raw_values[:limit]

    proxies = []
    for line in raw_values:
        try:
            proxy = reverse_parse_proxy(line)
        except InvalidFileLine as e:
            # Don't want to notify about blank lines.
            if e.line != "":
                log.error(str(e))
        else:
            proxies.append(proxy)

    if order_by:
        proxies = sorted(proxies, key=lambda x: getattr(x, order_by))
    return proxies


def write_proxies(method, proxies, overwrite=False):

    filepath = get_proxy_file_path(method)

    # This might actually happen when initially running app without files
    # (or if the user deletes it for whatever reason).
    if not filepath.exists():
        filepath.touch()

    add_proxies = proxies[:]
    if not overwrite:
        add_proxies = read_proxies(method)
        for proxy in proxies:
            if proxy not in add_proxies:
                add_proxies.append(proxy)

    for proxy in add_proxies:
        line = parse_proxy(proxy)
        filepath.write(line)


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
