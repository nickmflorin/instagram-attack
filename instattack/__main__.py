#!/usr/bin/env python3 -B
import argparse
from dotenv import load_dotenv
from plumbum import local  # noqa
import signal

from .db import database_init
from .lib import (
    AppLogger, apply_external_loggers, disable_external_loggers,
    progressbar_wrap, cancel_remaining_tasks, validate_log_level,
    get_env_file, dir_str, write_env_file)

from .cli.base import Instattack
from .cli.proxies import *  # noqa
from .cli.attack import *  # noqa
from .cli.users import *  # noqa


log = AppLogger(__name__)


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
    extra = {}
    if 'message' in context:
        extra['other'] = context['message']

    log.critical('Found error in exception handler.')
    exc = context['exception']
    log.traceback(exc)

    try:
        log.info('Shutting Down in Exception Handler')
        loop.run_until_complete(shutdown(loop))
    except RuntimeError:
        log.error('Loop was already shutdown... this should not be happening.')
        pass


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
    log.info('Loading .env file.')
    load_dotenv(dotenv_path=dir_str(filepath))


def start(loop, args):

    setup_environment(args)
    log.updateLevel()

    # Because we are having problems...
    loop.run_until_complete(tortoise.Tortoise.close_connections())

    setup_loop(loop)

    log.critical("""
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
        # We might not need this here because of the exception handler.
        except Exception as e:
            log.critical('Found error in exception block.')
            log.traceback(e)
        finally:
            # We have to do this just in case errors are caught by both the
            # handler and the catch block, until we figure out how to handle that,
            # since we cannot shut down the loop twice.
            # >>> RuntimeError: This event loop is already running
            log.info('Shutting Down in Finally Block')
            try:
                shutdown(loop)
            except RuntimeError:
                log.error('Loop was already shutdown... this should not be happening.')
                loop.run_until_complete(tortoise.Tortoise.close_connections())


def shutdown(loop, signal=None):
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
