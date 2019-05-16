from argparse import ArgumentTypeError
from plumbum.path import LocalPath, Path

from instattack.settings import LEVELS, METHODS, ROOT_DIR, dir_str


__all__ = ('validate_log_level', 'validate_method', 'is_numeric',
    'validate_config_filepath', 'validate_config_schema', )


def is_numeric(value):
    try:
        float(value)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return None
    else:
        try:
            return int(value)
        except ValueError:
            return float(value)
        else:
            if float(value) == int(value):
                return int(value)
            return float(value)


def validate_log_level(val):
    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in LEVELS:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


def validate_method(value):
    if value.upper() not in METHODS:
        raise ArgumentTypeError('Invalid method.')
    return value.upper()


def validate_config_filepath(value):
    """
    Validates the path specified or defaulted for the configuration file.  If the
    file cannot be found at the top level of the application, it will check the
    path as an absolute path on the local machine.

    TODO
    ----
    For error messages, indicate whether or not the path error was because we
    couldn't find it in the root directory or because the specified path was
    invalid.

    We might not need all of the validations for each case, maybe just the
    last two.
    """
    def _validate_path(path):
        if not path.dirname.exists():
            raise ArgumentTypeError(f'The path {value} does not exist.')

        if path.exists() and not path.is_file():
            raise ArgumentTypeError(f'The path {value} does not specify a config file.')

        if path.suffix not in ('.yml', '.yaml'):
            raise ArgumentTypeError('The configuration file must be a YAML file.')

        if not path.exists():
            if path.suffix == '.yml':
                path = path.with_suffix('.yaml')
            else:
                path = path.with_suffix('.yml')

        if not path.exists():
            raise ArgumentTypeError(f'The path {value} does not exist.')
        return dir_str(path)

    root_path = ROOT_DIR / Path(value)
    try:
        return _validate_path(root_path)
    except ArgumentTypeError:
        root_path = LocalPath(value)
        try:
            return _validate_path(root_path)
        except ArgumentTypeError as e:
            raise e


def validate_config_schema(config):
    """
    Using Cerebrus Package

    http://docs.python-cerberus.org/en/stable/schemas.html
    """
    schema_text = '''
    log:
        proxies: True

    token
        timeout = 10
        batch_size = 10
        max_tries = 20

        connection:
            limit_per_host: 0
            force_close: False
            timeout: 5
            limit: 50

        proxies
            prepopulate: True
            collect: False

            pool
                max_resp_time: 8
                max_error_rate: 0.5
                min_req_proxy: 6
                timeout: 25
                limit: 50
                prepopulate_limit: 50

            broker
                max_conn: 50
                max_tries: 2
                timeout: 5


    login
        pwlimit:
            type: int
            min: 0
        batch_size:
            type: int
            min: 0
        attempt_batch_size:
            type: int
            min: 0

        connection:
            limit_per_host: 0
            force_close: False
            timeout: 5
            limit: 200

        proxies
            prepopulate: True
            collect: False

            pool:
                max_resp_time: 6
                max_error_rate: 0.5
                min_req_proxy: 6
                timeout: 25
                limit: 200
                prepopulate_limit: 200

            broker:
                max_conn: 200
                max_tries: 2
                timeout: 5
    '''
