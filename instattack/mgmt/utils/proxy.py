from __future__ import absolute_import

from collections import Counter

from instattack import settings
from instattack.lib.logger import AppLogger
from instattack.lib.utils import validate_method

from instattack.models import RequestProxy
from instattack.mgmt.exceptions import InvalidFileLine

from .io import write_array_data, read_raw_data, stream_raw_data
from .paths import get_proxy_file_path


log = AppLogger(__file__)


__all__ = ('write_proxies', 'read_proxies_from_txt', )


def parse_proxy(proxy):
    return (
        f"{proxy.host}:{proxy.port},"
        f"{proxy.avg_resp_time},{proxy.error_rate}"
    )


def reverse_parse_proxy(index, line, method):
    HOST = 'host'
    PORT = 'port'
    AVG_RESP_TIME = 'avg_resp_time'
    ERROR_RATE = 'error_rate'

    scheme = settings.DEFAULT_SCHEMES[method]
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

    return RequestProxy(
        host=host,
        port=port,
        method=method,
        avg_resp_time=avg_resp_time,
        error_rate=error_rate,
        errors=Counter(),
        saved=True,
        # Have to include so that the pool can handle them appropriately.
        schemes=(scheme, ),
    )


def read_proxies_from_txt(method, limit=None):
    method = validate_method(method)
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
            proxy = reverse_parse_proxy(i, line, method)
        except InvalidFileLine as e:
            # Should not be an empty line because those should have been removed
            # in the read_raw_data method.
            log.error(e)
        else:
            if proxy.address not in [p.address for p in proxies]:
                proxies.append(proxy)
            else:
                log.warning(f'Found Duplicate Proxy in {filepath.name}.',
                    extra={'proxy': proxy})

    return proxies


def write_proxies(method, proxies, overwrite=False):

    filepath = get_proxy_file_path(method)

    # This might actually happen when initially running app without files
    # (or if the user deletes it for whatever reason).
    if not filepath.exists():
        filepath.touch()

    new_proxies = []
    if not overwrite:
        existing_proxies = read_proxies_from_txt(method)
        for proxy in proxies:
            if proxy not in existing_proxies and proxy not in new_proxies:
                new_proxies.append(proxy)

    all_proxies = new_proxies + existing_proxies
    to_write = [parse_proxy(proxy) for proxy in all_proxies]
    if len(new_proxies) == 0:
        log.error('No new proxies to save.')
    else:
        log.notice(f'Writing {len(new_proxies)} Unique Proxies to {filepath.name}.')
    log.notice(f'Now {len(all_proxies)} Proxies in {filepath.name}.')
    write_array_data(filepath, to_write)
