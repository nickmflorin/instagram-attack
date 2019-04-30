from __future__ import absolute_import

from collections import Counter

from instattack.settings import get_proxy_file_path
from instattack.logger import AppLogger
from instattack.utils import write_array_data, read_raw_data
from instattack.exceptions import InvalidFileLine

from .models import Proxy


log = AppLogger(__file__)


def parse_proxy(proxy):
    return (
        f"{proxy.host}:{proxy.port},"
        f"{proxy.avg_resp_time},{proxy.error_rate}"
    )


def reverse_parse_proxy(index, line):
    HOST = 'host'
    PORT = 'port'
    AVG_RESP_TIME = 'avg_resp_time'
    ERROR_RATE = 'error_rate'

    line = line.strip()

    # TODO: We probably shouldn't issue a warning if this is the case and just
    # silently ignore.
    if line == "":
        raise InvalidFileLine(index, line)

    if ',' not in line:
        raise InvalidFileLine(index, line, 'No comma separation.')

    pieces = line.split(',')
    if len(pieces) != 3:
        raise InvalidFileLine(index, line, 'Invalid comma separation.')

    try:
        address = pieces[0]
    except IndexError:
        raise InvalidFileLine(index, line, 'Invalid comma separation.')
    else:
        if ':' not in address:
            raise InvalidFileLine(index, line, reason='Missing `:`')
        address_parts = address.split(':')
        if len(address_parts) != 2:
            raise InvalidFileLine(index, line, reason='Address invalid.')

    try:
        host = str(address_parts[0])
    except IndexError:
        raise InvalidFileLine(index, line, reason='Address invalid.')
    except (ValueError, TypeError):
        raise InvalidFileLine(index, line, f'Invalid {HOST} type coercion.')

    try:
        port = int(address_parts[1])
    except IndexError:
        raise InvalidFileLine(index, line, reason='Address invalid.')
    except (ValueError, TypeError):
        raise InvalidFileLine(index, line, f'Invalid {PORT} type coercion.')

    try:
        avg_resp_time = float(pieces[1])
    except IndexError:
        raise InvalidFileLine(index, line, 'Invalid comma separation.')
    except (ValueError, TypeError):
        raise InvalidFileLine(index, line, f'Invalid {AVG_RESP_TIME} type coercion.')

    try:
        error_rate = float(pieces[2])
    except IndexError:
        raise InvalidFileLine(index, line, 'Invalid comma separation.')
    except (ValueError, TypeError):
        raise InvalidFileLine(index, line, f'Invalid {ERROR_RATE} type coercion.')

    return Proxy(
        host=host,
        port=port,
        avg_resp_time=avg_resp_time,
        error_rate=error_rate,
        errors=Counter()
    )


def read_proxies(method, limit=None, order_by=None):

    filepath = get_proxy_file_path(method)

    # This might actually happen when initially running app without files
    # (or if the user deletes it for whatever reason).
    if not filepath.exists():
        filepath.touch()

    if not filepath.is_file():
        raise FileNotFoundError('No such file: %s' % filepath)

    raw_values = read_raw_data(filepath, limit=limit)

    proxies = []
    for i, line in enumerate(raw_values):
        try:
            proxy = reverse_parse_proxy(i, line)
        except InvalidFileLine as e:
            # Should not be an empty line because those should have been removed
            # in the read_raw_data method.
            log.error(e)
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
    write_array_data(filepath, to_write)
