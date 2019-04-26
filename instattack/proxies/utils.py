from __future__ import absolute_import

import subprocess
from plumbum import local

from instattack.conf import settings
from instattack.conf.utils import validate_method

from instattack.logger import AppLogger
from instattack.utils import convert_lines_to_text

from .models import Proxy
from .exceptions import InvalidFileLine


log = AppLogger(__file__)


def parse_proxy(proxy):
    return (
        f"{proxy.host}:{proxy.port},"
        f"{proxy.avg_resp_time},{proxy.error_rate}"
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


def filter_proxy(proxy, max_error_rate=None, max_resp_time=None):
    if max_error_rate and proxy.error_rate > max_error_rate:
        return (None, 'max_error_rate')

    if max_resp_time and proxy.avg_resp_time > max_resp_time:
        return (None, 'max_resp_time')
    return (proxy, None)


def filter_proxies(proxies, max_error_rate=None, max_resp_time=None):
    return [
        filtered_proxy[0] for filtered_proxy in [
            filter_proxy(proxy, max_error_rate=max_error_rate, max_resp_time=max_resp_time)
            for proxy in proxies
        ] if filtered_proxy[0] is not None
    ]


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

    to_write = [parse_proxy(proxy) for proxy in add_proxies]
    data = convert_lines_to_text(to_write)
    filepath.write(data, encoding='utf-8')
