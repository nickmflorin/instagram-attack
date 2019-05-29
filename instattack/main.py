#!/usr/bin/env python3
import asyncio
import inspect
import logging
import pathlib
import signal
import tortoise

from cement import App, TestApp, init_defaults
from cement.core.exc import CaughtSignal

from instattack import settings
from instattack.conf import Configuration

from instattack.lib import logger
from instattack.lib.utils import (
    spin_start_and_stop, get_app_stack_at, task_is_third_party,
    cancel_remaining_tasks, start_and_stop)

from .app.exceptions import InstattackError
from .controllers.base import Base

import time


_shutdown = False

# You can log all uncaught exceptions on the main thread by assigning a handler
# to sys.excepthook.
# def exception_hook(exc_type, exc_value, exc_traceback):
#     log = logger.get_sync(__name__)
#     log.traceback(exc_type, exc_value, exc_traceback)


# sys.excepthook = exception_hook


# Configuration Defaults
CONFIG = init_defaults('instattack')
CONFIG['instattack']['foo'] = 'bar'


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


def setup(app):
    """
    [x] TODO:
    --------
    Use spinner for overall setup and shutdown methods and use the spinner.write()
    method to notify of individual tasks in the methods.
    """

    async def setup_config(loop):
        # Temporarily Set Path as Hardcoded Value
        config = Configuration(path="conf.yaml")
        config.read()
        config.set()

    @spin_start_and_stop('Setting Up Directories')
    async def setup_directories(loop):
        # Remove __pycache__ Files
        time.sleep(0.5)

        [p.unlink() for p in pathlib.Path(settings.APP_DIR).rglob('*.py[co]')]
        [p.rmdir() for p in pathlib.Path(settings.APP_DIR).rglob('__pycache__')]

        if not settings.USER_PATH.exists():
            settings.USER_PATH.mkdir()

    @spin_start_and_stop('Setting Up DB')
    async def setup_database(loop):
        time.sleep(0.5)
        await tortoise.Tortoise.init(config=settings.DB_CONFIG)
        await tortoise.Tortoise.generate_schemas()

    @spin_start_and_stop('Setting Up Loop')
    async def setup_loop(loop):

        SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

        time.sleep(0.5)
        loop.set_exception_handler(handle_exception)
        for s in SIGNALS:
            loop.add_signal_handler(s, shutdown_preemptively)

    @spin_start_and_stop('Setting Up Logger')
    async def setup_logger(loop):
        time.sleep(0.5)
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
    loop.run_until_complete(setup_config(loop))


@spin_start_and_stop('Shutting Down DB')
async def shutdown_database(loop):
    time.sleep(0.5)
    await tortoise.Tortoise.close_connections()


async def shutdown_outstanding_tasks(loop):
    with start_and_stop('Shutting Down Outstanding Tasks') as spinner:

        futures = await cancel_remaining_tasks(
            raise_exceptions=True,
            log_tasks=True
        )
        if len(futures) != 0:
            spinner.write(f'  > Cancelled {len(futures)} Leftover Tasks')

            log_tasks = futures[:20]
            for i, task in enumerate(log_tasks):
                if task_is_third_party(task):
                    spinner.write(f'  >> [{i + 1}] {task._coro.__name__} (Third Party)')
                else:
                    spinner.write(f'  >> [{i + 1}] {task._coro.__name__}')

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
