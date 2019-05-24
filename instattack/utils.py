from argparse import ArgumentTypeError
from plumbum.path import LocalPath, Path

from instattack import settings


def get_app_stack_at(stack, step=1):
    frames = [
        frame for frame in stack
        if frame.filename.startswith(settings.APP_ROOT)
    ]
    return frames[step]


def relative_to_root(path):

    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    # This only happens for the test.py file...  We should remove this conditional
    # when we do not need that functionality anymore.
    if settings.APP_NAME in path.parts:
        ind = path.parts.index(settings.APP_NAME)
        parts = path.parts[ind:]
        path = LocalPath(*parts)

    return settings.DIR_STR(path)


def percentage(num1, num2):
    return f"{'{0:.2f}'.format((num1 / num2 * 100))} %"


def task_is_third_party(task):
    """
    Need to find a more sustainable way of doing this, this makes
    sure that we are not raising exceptions for external tasks.
    """
    directory = get_task_path(task)
    return not directory.startswith(settings.APP_ROOT)


def get_coro_path(coro):
    return coro.cr_code.co_filename


def get_task_path(task):
    return get_coro_path(task._coro)


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
    from .settings import LEVELS
    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in LEVELS:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


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
    pass
