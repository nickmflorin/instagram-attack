#!/usr/bin/env python3
import asyncio
import pathlib

from cement import App, TestApp, init_defaults
from cement.core.exc import CaughtSignal

import tortoise

from instattack import settings
from instattack.lib import logger
from instattack.lib.utils import start_and_stop

from .app.exceptions import InstattackError
from .controllers.base import Base

import time


# Configuration Defaults
CONFIG = init_defaults('instattack')
CONFIG['instattack']['foo'] = 'bar'


async def setup_directories(loop):
    with start_and_stop('Setting Up Directories'):
        # Remove __pycache__ Files
        [p.unlink() for p in pathlib.Path(settings.APP_DIR).rglob('*.py[co]')]
        [p.rmdir() for p in pathlib.Path(settings.APP_DIR).rglob('__pycache__')]

        if not settings.USER_PATH.exists():
            settings.USER_PATH.mkdir()


async def setup_database(loop):
    with start_and_stop('Setting Up Database'):
        time.sleep(1)
        await tortoise.Tortoise.init(config=settings.DB_CONFIG)
        await tortoise.Tortoise.generate_schemas()


def setup(app):

    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_directories(loop))
    loop.run_until_complete(setup_database(loop))


async def shutdown_database(loop):
    with start_and_stop('Shutting Down DB'):
        time.sleep(1)
        await tortoise.Tortoise.close_connections()


def shutdown(app):

    loop = asyncio.get_event_loop()
    loop.run_until_complete(shutdown_database(loop))
    loop.close()


class Instattack(App):

    class Meta:
        label = 'instattack'

        config_defaults = CONFIG  # Configuration Defaults
        exit_on_close = True  # Call sys.exit() on Close

        # Laod Additional Framework Extensions
        extensions = ['yaml', 'colorlog', 'jinja2']

        config_handler = 'yaml'
        config_file_suffix = '.yml'

        log_handler = 'colorlog'  # Set the Log Handler
        output_handler = 'jinja2'  # Set the Output Handler

        hooks = [
            ('pre_setup', setup),
            ('post_run', shutdown),
        ]

        # Register Handlers
        handlers = [
            Base
        ]


class InstattackTest(TestApp, Instattack):

    class Meta:
        label = 'instattack'


def main():
    with Instattack() as app:
        try:
            app.run()

        except AssertionError as e:
            print('AssertionError > %s' % e.args[0])
            app.exit_code = 1

            if app.debug is True:
                import traceback
                traceback.print_exc()

        except InstattackError as e:
            print('InstattackError > %s' % e.args[0])
            app.exit_code = 1

            if app.debug is True:
                import traceback
                traceback.print_exc()

        except CaughtSignal as e:
            # Default Cement signals are SIGINT and SIGTERM, exit 0 (non-error)
            print('\n%s' % e)
            app.exit_code = 0


if __name__ == '__main__':
    main()


# def main():
#     from instattack.conf import Configuration
#     from instattack.conf.utils import validate_log_level

#     # We have to retrieve the --level at the top level and then use it to set
#     # the environment variable - which is in turn used to configure the loggers.
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--level', default='INFO', type=validate_log_level, dest='level')
#     parser.add_argument('--config', default='conf.yml', type=Configuration.validate, dest='config')

#     parsed, unknown = parser.parse_known_args()

#     loop = asyncio.get_event_loop()

#     os.environ['INSTATTACK_LOG_LEVEL'] = parsed.level.name

#     config = Configuration(path=parsed.config)

#     # Wait to import from src directory until LEVEL set in os.environ so that
#     # loggers are all created with correct level.
#     from .app.run import operator
#     oper = operator(config)
#     oper.start(loop, *unknown)
#     loop.close()
