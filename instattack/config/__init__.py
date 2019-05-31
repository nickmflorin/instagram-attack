from cement import init_defaults
import os

from .settings import APP_NAME, ROOT_DIR


__CONFIG__ = init_defaults(APP_NAME, 'log.logging')

# Have to Figure Out How to Tie in Cement Logger with Our Logger
__CONFIG__['log.logging']['level'] = 'info'

__CONFIG_DIRS__ = [os.path.join(ROOT_DIR, 'config')]
__CONFIG_FILES__ = [f'{APP_NAME}.yml']
__CONFIG_SECTION__ = APP_NAME

__EXTENSIONS__ = ['yaml', 'colorlog', 'jinja2']
__CONFIG_HANDLER__ = 'yaml'
__CONFIG_FILE_SUFFIX__ = '.yml'

__LOG_HANDLER__ = 'colorlog'
__OUTPUT_HANDLER__ = 'jinja2'

__EXIT_ON_CLOSE__ = True
