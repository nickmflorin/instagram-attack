#!/usr/bin/env python3 -B
from plumbum import local  # noqa

from dotenv import load_dotenv

from .exceptions import EnvFileMissing
from .lib import AppLogger, log_environment, get_env_file, dir_str

from .cli.base import Instattack
from .cli.proxies import *  # noqa
from .cli.attack import *  # noqa
from .cli.users import *  # noqa


log = AppLogger(__file__)


def load_environment():
    """
    Not currently putting anything in .env file but we may want to use this
    functionality.
    """
    try:
        filepath = get_env_file()
    except EnvFileMissing as e:
        filepath.touch()

    e = Exception('balh')
    log.info(e)
    log.info('Loading .env file.')
    log.warning('We probably do not have to do this anymore...')
    load_dotenv(dotenv_path=dir_str(filepath))


def main():
    # Have to figure out how to make the level an argument we use before going
    # into the CLI application.

    # Log environment is now only for progress bar, we can probably deprecate
    # that.
    with log_environment():
        load_environment()
        Instattack.run()


if __name__ == '__main__':
    main()
