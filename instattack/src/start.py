#!/usr/bin/env python3
from argparse import ArgumentTypeError
import logging
import pathlib
import signal
import sys
import tortoise
from tortoise import Tortoise

from instattack import logger
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


async def setup_database():
    await Tortoise.init(config=DB_CONFIG)

    # Generate the schema
    await Tortoise.generate_schemas()


def handle_exception(loop, context):
    """
    We are having trouble using log.exception() with exc_info=True and seeing
    the stack trace, so we have a custom log.traceback() method for now.

    >>> self.log.exception(exc, exc_info=True, extra=extra)

    Not sure if we will keep it or not, since it might add some extra
    customization availabilities, but it works right now.
    """
    log = SyncLogger(f"{__name__}:handle_exception")

    extra = {}
    if 'message' in context:
        extra['other'] = context['message']

    exc = context['exception']
    log.traceback(exc)

    shutdown(loop)


def setup_loop(loop):
    loop.set_exception_handler(handle_exception)
    loop.run_until_complete(setup_database())
    for s in SIGNALS:
        loop.add_signal_handler(s, shutdown)


def remove_pycache_files():
    root = get_app_root()
    [p.unlink() for p in pathlib.Path(dir_str(root)).rglob('*.py[co]')]
    [p.rmdir() for p in pathlib.Path(dir_str(root)).rglob('__pycache__')]


def setup_directories():
    remove_pycache_files()
    if not USER_DIR.exists():
        USER_DIR.mkdir()


def setup_logger():
    disable_external_loggers(
        'proxybroker',
        'aiosqlite',
        'db_client',
        'progressbar.utils',
        'tortoise'
    )


def setup(loop):
    setup_directories()
    setup_logger()

    # Because we sometimes have problems with this...
    # loop.run_until_complete(tortoise.Tortoise.close_connections())

    setup_loop(loop)


def shutdown_async_loggers(loop, log):

    loggers = [logging.getLogger(name)
        for name in logging.root.manager.loggerDict]

    for lgr in loggers:
        if isinstance(lgr, AsyncLogger):
            log.start('Shutting Down Logger...')
            loop.run_until_complete(lgr.shutdown())


def shutdown(loop, config=None, signal=None):
    log = logger.get_sync('Shutdown')

    if signal:
        log.warning(f'Received exit signal {signal.name}...')

    # Temporary Issue - We cannot pass in the config object from the loop
    # exception handler, only from teh start() method.  Eventually we might
    # want to find a better way to do this.
    if config:
        log.disable_on_true(config['log'].get('silent_shutdown'))

    log.start('Starting Shut Down')

    log.start('Shutting Down Async Loggers')
    shutdown_async_loggers(loop, log)
    log.complete('Async Loggers Shutdown')

    log.start('Cancelling Tasks')
    cancelled = loop.run_until_complete(cancel_remaining_tasks())
    if len(cancelled) != 0:
        log.complete(f'Cancelled {len(cancelled)} Tasks')
        log.before_lines()
        for task in cancelled:
            log.line(task._coro.__name__)
    else:
        log.complete('No Leftover Tasks to Cancel')

    log.start('Shutting Down Database')
    loop.run_until_complete(tortoise.Tortoise.close_connections())
    log.complete('Database Shutdown')

    loop.stop()
    log.complete('Shutdown Complete')


def start(loop, config, *a):

    log = SyncLogger(f"{__name__}:start")

    setup(loop)
    log.updateLevel()

    cli_args = sys.argv
    cli_args = [ag for ag in cli_args if '--level' not in ag and '--config' not in ag]

    # It would be easier if there was a way to pass this through to the CLI
    # application directly, instead of storing as ENV variable.
    config.store()

    with progressbar_wrap():
        try:
            EntryPoint.run(argv=cli_args)
        except (ArgumentTypeError, ArgumentError) as e:
            log.error(e)
        finally:
            shutdown(loop, config=config)
