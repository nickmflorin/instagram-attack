from argparse import ArgumentTypeError
from cerberus import Validator
from plumbum.path import LocalPath, Path

from instattack import settings
from instattack.app.exceptions import ConfigurationError


def validate_log_level(val):
    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        try:
            return settings.LoggingLevels[val.upper()]
        except KeyError:
            raise ArgumentTypeError("Invalid log level.")


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
        return settings.DIR_STR(path)

    root_path = settings.GET_ROOT() / Path(value)
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
    def positive_int(**kwargs):
        config = {
            'required': True,
            'type': 'integer',
            'min': 0,
        }
        config.update(**kwargs)
        return config

    def positive_float(**kwargs):
        config = {
            'required': True,
            'type': 'float',
            'min': 0.0,
        }
        config.update(**kwargs)
        return config

    def boolean(**kwargs):
        config = {
            'required': True,
            'type': 'boolean'
        }
        config.update(**kwargs)
        return config

    def log_level(**kwargs):
        to_level = lambda v: v.upper()  # noqa
        config = {
            'required': True,
            'type': 'string',
            # 'coerce': (str, to_level),
        }
        config.update(**kwargs)
        return config

    v = Validator()

    v.schema = {
        'log': {
            'required': True,
            'type': 'dict',
            'schema': {
                'operator': log_level(default='INFO'),
                'proxy_broker': log_level(default='WARNING'),
                'login_attempts': log_level(default='ERROR'),
                'proxy_pool': log_level(default='WARNING'),
            }
        },
        'login': {
            'required': True,
            'type': 'dict',
            'schema': {
                'limit': positive_int(max=10000, nullable=True, default=None),
                'batch_size': positive_int(max=100),
                'attempts': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'batch_size': positive_int(max=100),
                    }
                },
                'connection': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'limit_per_host': positive_int(max=100, default=10),
                        'timeout': positive_int(max=20, default=10),
                        # Might want to raise this max value higher.
                        'limit': positive_int(max=200, default=100),
                    }
                }
            }
        },
        'proxies': {
            'required': True,
            'type': 'dict',
            'schema': {
                'collect': boolean(),
                'prepopulate': boolean(),
                'pool': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'remove_proxy_on_error': boolean(default=False),
                        'max_conn': positive_int(max=1000, default=100),
                        'timeout': positive_int(max=50, default=25),

                        'max_ssl_errors': positive_int(nullable=True),
                        'max_connection_errors': positive_int(nullable=True),
                        'max_timeout_errors': positive_int(nullable=True),
                        'max_instagram_errors': positive_int(nullable=True),
                        'max_response_errors': positive_int(nullable=True),

                        'max_error_rate': positive_float(max=1.0, nullable=True),
                        'max_resp_time': positive_float(max=10.0, nullable=True),
                        'max_requests': positive_int(nullable=True),

                        'error_rate_horizon': positive_int(max=10),
                        'time_between_request_timeout': positive_int(default=10),
                    }
                },
                'broker': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'max_conn': positive_int(max=1000),
                        'max_tries': positive_int(max=10),
                        'timeout': positive_int(max=10),
                    },
                },
            }
        }
    }

    validated = v.validate(config)
    if not validated:
        raise ConfigurationError(v.errors)
