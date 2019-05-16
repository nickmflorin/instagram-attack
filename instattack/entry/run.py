#!/usr/bin/env python3
from argparse import ArgumentTypeError
from dotenv import load_dotenv
import os
import pathlib
import signal
import tortoise
from tortoise import Tortoise

from instattack.settings import USER_DIR, DB_CONFIG
from instattack.logger import (
    AppLogger, apply_external_loggers, disable_external_loggers, progressbar_wrap)
from instattack.lib import get_env_file, write_env_file
from instattack.utils import cancel_remaining_tasks, dir_str, get_app_root

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
    log = AppLogger(f"{__name__}:handle_exception")

    extra = {}
    if 'message' in context:
        extra['other'] = context['message']

    exc = context['exception']
    log.traceback(exc)

    loop.run_until_complete(shutdown(loop))


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
        'progressbar.utils'
    )
    apply_external_loggers('tortoise')


def setup_environment(args):
    if hasattr(args, 'level'):
        write_env_file({'level': args.level})
    filepath = get_env_file()
    load_dotenv(dotenv_path=dir_str(filepath))


def setup(loop, args):
    setup_environment(args)
    setup_directories()
    setup_logger()
    # Because we sometimes have problems with this...
    # loop.run_until_complete(tortoise.Tortoise.close_connections())

    setup_loop(loop)


def shutdown(loop, signal=None):
    log = AppLogger(f"{__name__}:shutdown")

    if signal:
        log.warning(f'Received exit signal {signal.name}...')

    log.conditional(os.environ.get('SILENT_SHUTDOWN'))

    log.start('Starting Shut Down')

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


def start(loop, args):

    log = AppLogger(f"{__name__}:start")

    setup(loop, args)
    log.updateLevel()

    # Log environment is now only for progress bar, we can probably deprecate
    # that.
    with progressbar_wrap():
        try:
            EntryPoint.run()
        except ArgumentTypeError as e:
            log.error(e)
        finally:
            shutdown(loop)
