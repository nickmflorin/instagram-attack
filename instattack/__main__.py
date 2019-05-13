#!/usr/bin/env python3
import argparse
import asyncio
from dotenv import load_dotenv
import pathlib
import signal
import tortoise

from .db import database_init
from .settings import dir_str, USER_DIR

from .logger import (
    AppLogger, apply_external_loggers, disable_external_loggers, progressbar_wrap)
from .lib import validate_log_level, get_env_file, write_env_file
from .core.utils import cancel_remaining_tasks
from .cli import Instattack

"""
May want to catch other signals too - these are not currently being
used, but could probably be expanded upon.
"""
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)


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


def remove_pycache_files():
    [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]
    [p.rmdir() for p in pathlib.Path('.').rglob('__pycache__')]


def setup_directories():
    remove_pycache_files()
    if not USER_DIR.exists():
        USER_DIR.mkdir()


def setup_loop(loop):
    loop.set_exception_handler(handle_exception)
    loop.run_until_complete(database_init())
    for s in SIGNALS:
        loop.add_signal_handler(s, shutdown)


def setup_logger():

    disable_external_loggers(
        'proxybroker',
        'aiosqlite',
        'db_client',
        'progressbar.utils'
    )
    apply_external_loggers('tortoise')


def setup_environment(args):
    write_env_file({'level': args.level})
    filepath = get_env_file()
    load_dotenv(dotenv_path=dir_str(filepath))


def start(loop, args):

    log = AppLogger(f"{__name__}:start")

    setup_environment(args)
    log.updateLevel()

    setup_directories()

    # Because we sometimes have problems with this...
    # loop.run_until_complete(tortoise.Tortoise.close_connections())

    setup_loop(loop)

    log.note("""
    Big problem right now is managing pool size even with prepoplulated proxies,
    we should only start pulling proxies in when the pool size is less than
    some threshold, that is less for the token requests, and then only start
    the broker if there are no prepopulated proxies left

    We should also look into saving proxy errors as a JSON dict instead of
    FOREIGN KEY, that way, we don't have to constantly be writing to the
    database and can just save the proxy afterwards.
    """)

    # Log environment is now only for progress bar, we can probably deprecate
    # that.
    with progressbar_wrap():
        try:
            Instattack.run()
        finally:
            shutdown(loop)


def shutdown(loop, signal=None):
    log = AppLogger(f"{__name__}:shutdown")

    if signal:
        log.warning(f'Received exit signal {signal.name}...')

    log.start('[!] Starting Shut Down')

    log.start('[x] Cancelling Tasks')
    loop.run_until_complete(cancel_remaining_tasks())

    log.start('[x] Shutting Down Database')
    loop.run_until_complete(tortoise.Tortoise.close_connections())

    loop.stop()
    log.complete('[!] Shutdown Complete')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--level', default='INFO', type=validate_log_level)
    args, unknown = parser.parse_known_args()

    loop = asyncio.get_event_loop()
    start(loop, args)
    loop.close()
