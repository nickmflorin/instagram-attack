from plumbum import local

from instattack import settings

from instattack.lib.utils import validate_method
from instattack.lib.logger import AppLogger

from instattack.mgmt.utils import read_raw_data
from instattack.mgmt.exceptions import InvalidFileLine

from .models import Proxy


log = AppLogger(__file__)


# Only keep for now just in case we have to reread proxies from text files.
def _proxy_file_dir(app_name=True):
    if app_name:
        return local.cwd / settings.APP_NAME / settings.DATA_DIR / settings.PROXY_DIR
    return local.cwd / settings.DATA_DIR / settings.PROXY_DIR


# Only keep for now just in case we have to reread proxies from text files.
def _get_proxy_data_dir():
    path = _proxy_file_dir()
    if not path.exists():
        path = _proxy_file_dir(app_name=False)
    return path


# Only keep for now just in case we have to reread proxies from text files.
def get_proxy_file_path(method):
    """
    `app_name` just allows us to run commands from the level deeper than the root
    directory.

    TODO: Incorporate the checks just in case we have to construct the files and
    directories
    """
    path = _get_proxy_data_dir()

    validate_method(method)
    filename = "%s.txt" % method.lower()
    return path / filename


# Only keep for now just in case we have to reread proxies from text files.
def reverse_parse_proxy(index, line, method):
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
        method=method,
        avg_resp_time=avg_resp_time,
        error_rate=error_rate,
    )


# Only keep for now just in case we have to reread proxies from text files.
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
