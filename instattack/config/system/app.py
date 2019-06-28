import os
import signal

from instattack.info import __NAME__
from instattack.ext import get_root

CONFIG_SECTION = __NAME__

CONFIG_DIRS = [os.path.join(get_root(), 'config')]
CONFIG_FILES = [f'{__NAME__}.yml']

EXTENSIONS = ['yaml', 'colorlog', 'jinja2']
CONFIG_HANDLER = 'yaml'
CONFIG_FILE_SUFFIX = '.yml'
OUTPUT_HANDLER = 'jinja2'

EXIT_ON_CLOSE = True

SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
