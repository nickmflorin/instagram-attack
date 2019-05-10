#!/usr/bin/env python3 -B
from plumbum import local  # noqa

from dotenv import load_dotenv

from .cli.base import Instattack
from .cli.proxies import *  # noqa
from .cli.attack import *  # noqa
from .cli.users import *  # noqa

"""
Plumbum Modules That We Should Implement

Plumbum Docs
https://plumbum.readthedocs.io/en/latest/quickref.html

PROGNAME = Custom program name and/or color
VERSION = Custom version
DESCRIPTION = Custom description (or use docstring)
COLOR_GROUPS = Colors of groups (dictionary)
COLOR_USAGE = Custom color for usage statement

Plumbum Progress Bar
Plumbum Colors

Plumbum User Input
plumbum.cli.terminal.readline()
plumbum.cli.terminal.ask()
plumbum.cli.terminal.choose()
plumbum.cli.terminal.prompt()

.cleanup()
Method performed in cli.Application after all components of main() have completed.
"""


def load_environment():
    try:
        filepath = get_env_file()
    # We might not need to require the `.env` file to be present.
    except EnvFileMissing as e:
        log.warning(str(e))
        filepath.touch()
    else:
        log.info('Loading .env file.')
        load_dotenv(dotenv_path=dir_str(filepath))


def main():
    Instattack.run()


if __name__ == '__main__':
    main()
