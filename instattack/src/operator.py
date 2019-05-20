#!/usr/bin/env python3
from argparse import ArgumentTypeError
import logging
import pathlib
import signal
import sys
import tortoise
from tortoise import Tortoise

from instattack import logger
from instattack.conf import Configuration
from instattack.logger import (
    SyncLogger, AsyncLogger, disable_external_loggers, progressbar_wrap)
from instattack.lib import cancel_remaining_tasks

from instattack.conf.settings import USER_DIR, DB_CONFIG
from instattack.conf.utils import dir_str, get_app_root

from .exceptions import ArgumentError
from .cli import EntryPoint

"""
May want to catch other signals too - these are not currently being
used, but could probably be expanded upon.
"""
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)


class operator(object):

    def __init__(self, config):
        self.config = config
        self._shutdown = False

    def start(self, loop, *a):
        log = SyncLogger(f"{__name__}:start")

        self.setup(loop)
        log.updateLevel()

        cli_args = sys.argv
        cli_args = [ag for ag in cli_args if '--level' not in ag and '--config' not in ag]

        # It would be easier if there was a way to pass this through to the CLI
        # application directly, instead of storing as ENV variable.
        self.config.store()

        # with progressbar_wrap():
        try:
            EntryPoint.run(argv=cli_args)
        except (ArgumentTypeError, ArgumentError) as e:
            log.error(e)
        # Using finally here instead of else might cause race conditions with
        # shutdown, but we issue a warning if the shutdown was already performed.
        # If we don't use finally, than we cannot stop the program.
        finally:
            self.shutdown(loop)

    def setup(self, loop):
        self.setup_directories(loop)
        self.setup_logger(loop)
        self.setup_loop(loop)

    def shutdown(self, loop, signal=None):
        """
        For signal handlers, the shutdown() method requires the loop argument.
        For all shutdown related methods, we will require the loop method to be
        explicitly provided even though they could have access to self.loop if we
        initialized operator that way.
        """
        log = logger.get_sync('Shutdown')

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
            log.disable_on_true(config['log'].get('silent_shutdown'))

        log.start('Starting Shut Down')

        self.shutdown_async_loggers(loop, log)
        self.shutdown_outstanding_tasks(loop, log)
        self.shutdown_database(loop, log)

        loop.stop()
        log.complete('Shutdown Complete')

    def handle_exception(self, loop, context):
        """
        We are having trouble using log.exception() with exc_info=True and seeing
        the stack trace, so we have a custom log.traceback() method for now.

        >>> self.log.exception(exc, exc_info=True, extra=extra)

        Not sure if we will keep it or not, since it might add some extra
        customization availabilities, but it works right now.
        """
        log = SyncLogger(f"{__name__}:handle_exception")

        exc = context['exception']
        log.traceback(exc)

        log.debug('Shutting Down in Exception Handler')
        self.shutdown(loop)

    def shutdown_outstanding_tasks(self, loop, log):
        log.start('Cancelling Tasks')

        cancelled = loop.run_until_complete(cancel_remaining_tasks())
        if len(cancelled) != 0:

            log.before_lines()
            for task in cancelled[:20]:
                log.line(task._coro.__name__)

            if len(cancelled) > 20:
                log.line('...')

            log.complete(f'Cancelled {len(cancelled)} Tasks')
        else:
            log.complete('No Leftover Tasks to Cancel')

    def shutdown_async_loggers(self, loop, log):
        log.start('Shutting Down Async Loggers')

        loggers = [logging.getLogger(name)
            for name in logging.root.manager.loggerDict]

        for lgr in loggers:
            if isinstance(lgr, AsyncLogger):
                log.start('Shutting Down Logger...')
                loop.run_until_complete(lgr.shutdown())

        log.complete('Async Loggers Shutdown')

    def shutdown_database(self, loop, log):
        log.start('Shutting Down Database')
        loop.run_until_complete(tortoise.Tortoise.close_connections())
        log.complete('Database Shutdown')

    def setup_loop(self, loop):
        loop.set_exception_handler(self.handle_exception)
        loop.run_until_complete(self.setup_database(loop))
        for s in SIGNALS:
            loop.add_signal_handler(s, self.shutdown)

    def setup_directories(self, loop):
        self.remove_pycache_files(loop)
        if not USER_DIR.exists():
            USER_DIR.mkdir()

    def remove_pycache_files(self, loop):
        root = get_app_root()
        [p.unlink() for p in pathlib.Path(dir_str(root)).rglob('*.py[co]')]
        [p.rmdir() for p in pathlib.Path(dir_str(root)).rglob('__pycache__')]

    def setup_logger(self, loop):
        disable_external_loggers(
            'proxybroker',
            'aiosqlite',
            'db_client',
            'progressbar.utils',
            'tortoise'
        )

    async def setup_database(self, loop):
        await Tortoise.init(config=DB_CONFIG)
        await Tortoise.generate_schemas()
