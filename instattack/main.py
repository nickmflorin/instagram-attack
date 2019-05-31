#!/usr/bin/env python3
import asyncio
import inspect
import logging
import pathlib
import signal
import tortoise
import warnings

from cement import App, TestApp
from cement.core.exc import CaughtSignal

from instattack import config
from instattack.config import settings
from instattack.config.utils import validate_config_schema

from instattack.lib import logger
from instattack.lib.utils import (
    spin_start_and_stop, get_app_stack_at, task_is_third_party,
    cancel_remaining_tasks, start_and_stop, break_after, break_before,
    sync_spin_start_and_stop)

from .app.exceptions import InstattackError
from .controllers.base import Base, UserController, ProxyController


warnings.simplefilter('ignore')
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

_shutdown = False

# You can log all uncaught exceptions on the main thread by assigning a handler
# to sys.excepthook.
# def exception_hook(exc_type, exc_value, exc_traceback):
#     log = logger.get_sync(__name__)
#     log.traceback(exc_type, exc_value, exc_traceback)


# sys.excepthook = exception_hook


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


@spin_start_and_stop('Setting Up Loop')
def setup_loop(app):

    loop = asyncio.get_event_loop()
    setattr(loop, 'config', app.config)

    loop.set_exception_handler(handle_exception)
    for s in SIGNALS:
        loop.add_signal_handler(s, shutdown_preemptively)


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
        await tortoise.Tortoise.close_connections()
        await tortoise.Tortoise.init(config=settings.DB_CONFIG)
        await tortoise.Tortoise.generate_schemas()

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
                spinner.write("...")
        else:
            spinner.write(f'No Leftover Tasks to Cancel')


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


@break_before
@break_after
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


class Instattack(App):

    class Meta:
        label = settings.APP_NAME

        # Default configuration dictionary.
        config_dirs = config.__CONFIG_DIRS__
        config_files = config.__CONFIG_FILES__
        config_section = config.__CONFIG_SECTION__

        exit_on_close = config.__EXIT_ON_CLOSE__  # Call sys.exit() on Close

        # Laod Additional Framework Extensions
        extensions = config.__EXTENSIONS__

        config_handler = config.__CONFIG_HANDLER__
        config_file_suffix = config.__CONFIG_FILE_SUFFIX__

        # Have to Figure Out How to Tie in Cement Logger with Our Logger
        log_handler = config.__LOG_HANDLER__
        output_handler = config.__OUTPUT_HANDLER__

        hooks = [
            ('pre_setup', setup),
            ('pre_run', ensure_logger_enabled),
            ('post_run', shutdown),
        ]

        # Register Handlers
        handlers = [
            Base,
            UserController,
            ProxyController,
        ]

    def run(self):
        self.loop = asyncio.get_event_loop()
        setattr(self.loop, 'config', self.config)
        super(Instattack, self).run()

    @break_after
    @sync_spin_start_and_stop('Validating Config')
    def validate_config(self):
        super(Instattack, self).validate_config()

        data = self.config.get_dict()['instattack']
        validate_config_schema({'instattack': data})


class InstattackTest(TestApp, Instattack):

    class Meta:
        label = settings.APP_NAME

        # Default configuration dictionary.
        config_dirs = config.__CONFIG_DIRS__
        config_files = config.__CONFIG_FILES__
        config_section = config.__CONFIG_SECTION__

        exit_on_close = config.__EXIT_ON_CLOSE__  # Call sys.exit() on Close

        # Laod Additional Framework Extensions
        extensions = config.__EXTENSIONS__

        config_handler = config.__CONFIG_HANDLER__
        config_file_suffix = config.__CONFIG_FILE_SUFFIX__

        hooks = [
            ('pre_setup', setup),
        ]

        # Register Handlers
        handlers = [
            Base,
        ]


def main():
    with Instattack() as app:

        # Wait for App Config to be Set
        setup_loop(app)

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
