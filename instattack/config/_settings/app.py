# from instattack.ext import get_root
# import os
# import signal

NAME = 'instattack'
FORMAL_NAME = NAME.title()
VERSION = (0, 0, 1, 'alpha', 0)

CONFIG_SECTION = NAME

# CONFIG_DIRS = [os.path.join(get_root(), 'config')]
CONFIG_FILES = [f'{NAME}.yml']

EXTENSIONS = ['yaml', 'colorlog', 'jinja2']
CONFIG_HANDLER = 'yaml'
CONFIG_FILE_SUFFIX = '.yml'
OUTPUT_HANDLER = 'jinja2'

EXIT_ON_CLOSE = True

# SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
