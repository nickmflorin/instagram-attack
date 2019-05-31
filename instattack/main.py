#!/usr/bin/env python3
import asyncio
import inspect
import logging
import os
import pathlib
import signal
import tortoise
import warnings

from cement import App, TestApp, init_defaults
from cement.core.exc import CaughtSignal

from instattack import settings
from instattack.conf import Configuration

from instattack.lib import logger
from instattack.lib.utils import (
    spin_start_and_stop, get_app_stack_at, task_is_third_party,
    cancel_remaining_tasks, start_and_stop, break_after, break_before)

from .app.exceptions import InstattackError
from .controllers.base import Base, UserController, ProxyController


warnings.simplefilter('ignore')

_shutdown = False

# You can log all uncaught exceptions on the main thread by assigning a handler
# to sys.excepthook.
# def exception_hook(exc_type, exc_value, exc_traceback):
#     log = logger.get_sync(__name__)
#     log.traceback(exc_type, exc_value, exc_traceback)


# sys.excepthook = exception_hook


# Configuration Defaults
# CONFIG = init_defaults('instattack')


def handle_exception(loop, context):
    """
    We are having trouble using log.exception() with exc_info=True and seeing
    the stack trace, so we have a custom log.traceback() method for now.

    >>> self.log.exception(exc, exc_info=True, extra=extra)

    Not sure if we will keep it or not, since it might add some extra
    customization availabilities, but it works right now.
    """
    log = logger.get_sync('handle_exception', sync=True)
    log.debug('Handling Exception')

    # Unfortunately, the step will only work for exceptions that are caught
    # at the immediate next stack.  It might make more sense to take the step
    # out.
    stack = inspect.stack()
    frame = get_app_stack_at(stack, step=1)

    # The only benefit including the frame has is that the filename
    # will not be in the logger, it will be in the last place before the
    # logger and this statement.
    try:
        log.traceback(
            context['exception'].__class__,
            context['exception'],
            context['exception'].__traceback__,
            extra={'frame': frame}
        )
    except BlockingIOError:
        log.warning('Could Not Output Traceback due to Blocking IO')

    log.debug('Shutting Down in Exception Handler')
    shutdown_preemptively(loop)


def ensure_logger_enabled(app):
    log = logger.get_sync(__name__, subname='ensure_logger_enabled')
    if not logger._enabled:
        log.warning('Logger Should be Enabled Before App Start')
        logger.enable()


def setup_config(app):
    """
    [x] TODO:
    ---------
    There is probably and most likely a better way to do this.  We can also set
    default config settings for specific handlers.

    >>> from cement.ext.ext_yaml import YamlConfigHandler
    >>> ins = YamlConfigHandler()
    >>> ins._setup(app)
    >>> ins.parse_file("/repos/instagram-attack/config/instattack.yml")
    """

    # Temporarily Set Path as Hardcoded Value
    # config = Configuration(filename="instattack.yml")
    # config.read()

    # # Right now, we don't need to worry about the other potential top level
    # # attributes.
    # # config = config['instattack']
    # app.config.merge(config.serialize())


@break_before
@break_after
def setup(app):
    """
    [x] TODO:
    --------
    Use spinner for overall setup and shutdown methods and use the spinner.write()
    method to notify of individual tasks in the methods.
    """
    @spin_start_and_stop('Setting Up Directories')
    async def setup_directories(loop):
        # Remove __pycache__ Files
        [p.unlink() for p in pathlib.Path(settings.APP_DIR).rglob('*.py[co]')]
        [p.rmdir() for p in pathlib.Path(settings.APP_DIR).rglob('__pycache__')]

        if not settings.USER_PATH.exists():
            settings.USER_PATH.mkdir()

    @spin_start_and_stop('Setting Up DB')
    async def setup_database(loop):
        await tortoise.Tortoise.init(config=settings.DB_CONFIG)
        await tortoise.Tortoise.generate_schemas()

    @spin_start_and_stop('Setting Up Loop')
    async def setup_loop(loop):

        SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

        loop.set_exception_handler(handle_exception)
        for s in SIGNALS:
            loop.add_signal_handler(s, shutdown_preemptively)

    @spin_start_and_stop('Setting Up Logger')
    async def setup_logger(loop):
        logger.disable_external_loggers(
            'proxybroker',
            'aiosqlite',
            'db_client',
            'progressbar.utils',
            'tortoise'
        )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_loop(loop))
    loop.run_until_complete(setup_logger(loop))
    loop.run_until_complete(setup_directories(loop))
    loop.run_until_complete(setup_database(loop))


@spin_start_and_stop('Shutting Down DB')
async def shutdown_database(loop):
    await tortoise.Tortoise.close_connections()


async def shutdown_outstanding_tasks(loop):
    with start_and_stop('Shutting Down Outstanding Tasks') as spinner:

        futures = await cancel_remaining_tasks()
        if len(futures) != 0:
            spinner.write(f'Cancelled {len(futures)} Leftover Tasks')

            spinner.indent()
            spinner.number()

            log_tasks = futures[:20]
            for i, task in enumerate(log_tasks):
                if task_is_third_party(task):
                    spinner.write(f'{task._coro.__name__} (Third Party)')
                else:
                    spinner.write(f'{task._coro.__name__}')

            if len(futures) > 20:
                spinner.write("  >> ...")
        else:
            spinner.write(f'  > No Leftover Tasks to Cancel')


@spin_start_and_stop('Shutting Down Async Loggers')
async def shutdown_async_loggers(loop):
    """
    [x] TODO:
    --------
    aiologger is still in Beta, and we continue to get warnings about the loggers
    not being shut down properly with .flush() and .close().  We should probably
    remove that dependency and just stick to the sync logger, since it does not
    improve speed by a substantial amount.
    """
    # This will return empty list right now.
    loggers = [
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict
    ]

    for lgr in loggers:
        if isinstance(lgr, logger.AsyncLogger):
            await lgr.shutdown()


def shutdown_preemptively(loop, signal=None):
    """
    The shutdown method that is tied to the Application hooks only accepts
    `app` as an argument, and we need the shutdown method tied to the exception
    hook to accept `loop` and `signal` - which necessitates the need for an
    alternate shutdown method.
    """
    log = logger.get_sync(__name__, subname='shutdown_preemptively')

    global _shutdown
    if _shutdown:
        log.warning('Instattack Already Shutdown...')
        return

    _shutdown = True

    if signal:
        log.warning(f'Received exit signal {signal.name}...')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(shutdown_async_loggers(loop))
    loop.run_until_complete(shutdown_outstanding_tasks(loop))
    loop.run_until_complete(shutdown_database(loop))
    loop.close()


@break_before
@break_after
def shutdown(app):
    """
    Race conditions can sometimes lead to multiple shutdown attempts, which can
    raise errors due to the loop state.  We check the global _shutdown status to
    make sure we avoid this and log in case it is avoidable.

    [x] TODO:
    --------
    Use spinner for overall setup and shutdown methods and use the spinner.write()
    method to notify of individual tasks in the methods.
    """
    log = logger.get_sync(__name__, subname='shutdown')

    global _shutdown
    if _shutdown:
        log.warning('Instattack Already Shutdown...')
        return

    _shutdown = True

    loop = asyncio.get_event_loop()
    loop.run_until_complete(shutdown_async_loggers(loop))
    loop.run_until_complete(shutdown_outstanding_tasks(loop))
    loop.run_until_complete(shutdown_database(loop))
    loop.close()


CONFIG = init_defaults('instattack', 'log.logging')
# Have to Figure Out How to Tie in Cement Logger with Our Logger
CONFIG['log.logging']['level'] = 'info'

CONFIG_DIRS = [os.path.join(settings.ROOT_DIR, 'config')]
CONFIG_FILES = ['instattack.yml']
CONFIG_SECTION = 'instattack'

EXTENSIONS = ['yaml', 'colorlog', 'jinja2']
CONFIG_HANDLER = 'yaml'
CONFIG_FILE_SUFFIX = '.yml'

EXIT_ON_CLOSE = True

class Instattack(App):

    class Meta:
        label = 'instattack'

        # Default configuration dictionary.
        # config_defaults = CONFIG
        config_dirs = CONFIG_DIRS
        config_files = CONFIG_FILES
        config_section = CONFIG_SECTION

        exit_on_close = EXIT_ON_CLOSE  # Call sys.exit() on Close

        # Laod Additional Framework Extensions
        extensions = EXTENSIONS

        config_handler = CONFIG_HANDLER
        config_file_suffix = CONFIG_FILE_SUFFIX

        # Have to Figure Out How to Tie in Cement Logger with Our Logger
        log_handler = 'colorlog'  # Set the Log Handler
        output_handler = 'jinja2'  # Set the Output Handler

        hooks = [
            ('pre_setup', setup),
            ('post_setup', setup_config),
            ('pre_run', ensure_logger_enabled),
            ('post_run', shutdown),
        ]

        # Register Handlers
        handlers = [
            Base,
            UserController,
            ProxyController,
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
            print('InstattackError > %s' % settings.LoggingLevels.ERROR(str(e)))
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
