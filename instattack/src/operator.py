#!/usr/bin/env python3
from argparse import ArgumentTypeError
import inspect
import logging
import os
import pathlib
import signal
import sys
import tortoise

# Need to figure out how to delay import of this module totally until LEVEL set
# in os.environ, or finding a better way of setting LEVEL with CLI.
from instattack import logger, settings
from instattack.exceptions import ArgumentError

from instattack.conf import Configuration
from instattack.src.utils import get_app_stack_at, task_is_third_party, cancel_remaining_tasks

from .cli import EntryPoint

"""
May want to catch other signals too - these are not currently being
used, but could probably be expanded upon.
"""
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)


# You can log all uncaught exceptions on the main thread by assigning a handler
# to sys.excepthook.
def exception_hook(exc_type, exc_value, exc_traceback):
    log = logger.get_sync(__name__)
    log.traceback(exc_type, exc_value, exc_traceback)


sys.excepthook = exception_hook


class shutdown_mixin(object):

    def shutdown(self, loop, signal=None):
        """
        For signal handlers, the shutdown() method requires the loop argument.
        For all shutdown related methods, we will require the loop method to be
        explicitly provided even though they could have access to self.loop if we
        initialized operator that way. x
        """
        log = logger.get_sync('__name__', subname='shutdown')

        if self._shutdown:
            log.warning('Instattack Already Shutdown...')
            return

        self._shutdown = True
        if signal:
            log.warning(f'Received exit signal {signal.name}...')

        # It would be easier if there was a way to pass this through to the CLI
        # application directly, instead of storing as ENV variable.
        config = Configuration.load()

        # Temporary Issue - We cannot pass in the config object from the loop
        # exception handler, only from teh start() method.  Eventually we might
        # want to find a better way to do this.
        if config:
            log.disable_on_true(config.get('silent_shutdown', False))

        log.start('Starting Shut Down')
        loop.run_until_complete(self.shutdown_async(loop))
        loop.stop()
        log.complete('Shutdown Complete')

    async def shutdown_async(self, loop):
        await self.shutdown_outstanding_tasks(loop)
        await self.shutdown_async_loggers(loop)
        await self.shutdown_database(loop)

    async def shutdown_outstanding_tasks(self, loop):
        log = logger.get_sync(__name__, subname='shutdown_outstanding_tasks')

        log.start('Cancelling Remaining Tasks')
        futures = await cancel_remaining_tasks(raise_exceptions=True, log_tasks=True)
        if len(futures) != 0:
            log.complete(f'Cancelled {len(futures)} Leftover Tasks')

            with log.logging_lines():
                log_tasks = futures[:20]
                for task in log_tasks:
                    if task_is_third_party(task):
                        log.line(f"{task._coro.__name__} (Third Party)")
                    else:
                        log.line(task._coro.__name__)

                if len(futures) > 20:
                    log.line('...')
        else:
            log.complete('No Leftover Tasks to Cancel')

    async def shutdown_async_loggers(self, loop):
        from instattack.logger import AsyncLogger

        log = logger.get_async(__name__, subname='shutdown_async_loggers')

        await log.complete('Shutting Down Async Loggers')
        loggers = [logging.getLogger(name)
            for name in logging.root.manager.loggerDict]

        for lgr in loggers:
            if isinstance(lgr, AsyncLogger):
                log.start('Shutting Down Logger...')
                await lgr.shutdown()

        await log.complete('Async Loggers Shutdown')

    async def shutdown_database(self, loop):
        log = logger.get_async(__name__, subname='shutdown_database')
        await log.start('Shutting Down Database')
        await tortoise.Tortoise.close_connections()
        await log.complete('Database Shutdown')


class operator(shutdown_mixin):

    def __init__(self, config):
        if 'LEVEL' not in os.environ:
            raise RuntimeError('Level must be set.')
        self.config = config
        self._shutdown = False

    def start(self, loop, *a):
        from instattack.logger import progressbar_wrap
        log = logger.get_sync(__name__, subname='start')

        self.setup(loop)

        cli_args = sys.argv
        cli_args = [ag for ag in cli_args if '--level' not in ag and '--config' not in ag]

        # It would be easier if there was a way to pass this through to the CLI
        # application directly, instead of storing as ENV variable.
        self.config.set()

        with progressbar_wrap():
            try:
                EntryPoint.run(argv=cli_args)
            except (ArgumentTypeError, ArgumentError) as e:
                log.error(e)
            finally:
                # Using finally here instead of else might cause race conditions with
                # shutdown, but we issue a warning if the shutdown was already performed.
                # If we don't use finally, than we cannot stop the program.
                if not self._shutdown:
                    log.debug('Shutting Down in Start Method')
                    self.shutdown(loop)

    def setup(self, loop):
        self.setup_directories(loop)
        self.setup_logger(loop)
        self.setup_loop(loop)

    def setup_loop(self, loop):
        loop.set_exception_handler(self.handle_exception)
        loop.run_until_complete(self.setup_database(loop))
        for s in SIGNALS:
            loop.add_signal_handler(s, self.shutdown)

    def setup_directories(self, loop):
        self.remove_pycache_files(loop)
        if not settings.USER_PATH.exists():
            settings.USER_PATH.mkdir()

    def remove_pycache_files(self, loop):
        [p.unlink() for p in pathlib.Path(settings.APP_DIR).rglob('*.py[co]')]
        [p.rmdir() for p in pathlib.Path(settings.APP_DIR).rglob('__pycache__')]

    def setup_logger(self, loop):
        from instattack.logger import disable_external_loggers

        disable_external_loggers(
            'proxybroker',
            'aiosqlite',
            'db_client',
            'progressbar.utils',
            'tortoise'
        )

    async def setup_database(self, loop):
        await tortoise.Tortoise.init(config=settings.DB_CONFIG)
        await tortoise.Tortoise.generate_schemas()

    def handle_exception(self, loop, context):
        """
        We are having trouble using log.exception() with exc_info=True and seeing
        the stack trace, so we have a custom log.traceback() method for now.

        >>> self.log.exception(exc, exc_info=True, extra=extra)

        Not sure if we will keep it or not, since it might add some extra
        customization availabilities, but it works right now.
        """
        log = logger.get_sync(__name__, subname='handle_exception')
        log.debug('Handling Exception')

        # Unfortunately, the step will only work for exceptions that are caught
        # at the immediate next stack.  It might make more sense to take the step
        # out.
        stack = inspect.stack()
        frame = get_app_stack_at(stack, step=1)

        # The only benefit including the frame has is that the filename
        # will not be in the logger, it will be in the last place before the
        # logger and this statement.
        log.traceback(
            context['exception'].__class__,
            context['exception'],
            context['exception'].__traceback__,
            extra={'frame': frame}
        )

        log.debug('Shutting Down in Exception Handler')
        self.shutdown(loop)
