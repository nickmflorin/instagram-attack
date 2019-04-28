#!/usr/bin/env python3

from .base import Instattack
from .proxies import *  # noqa
from .attack import *  # noqa

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


def main():
    Instattack.run()


if __name__ == '__main__':
    main()
