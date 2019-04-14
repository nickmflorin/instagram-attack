from __future__ import absolute_import

import os
from platform import python_version
import signal
import logging

import asyncio
from argparse import ArgumentParser

from proxybroker import Broker

from app.engine import Engine
from app.lib import exceptions
from app.lib.logging import AppLogger, create_handlers
from app.lib.users import User
from app.lib.utils import (
    validate_proxy_sleep, validate_log_level, validate_limit)

# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = AppLogger(__file__)


class Configuration(object):

    def __init__(self, arguments):

        self.a_sync = arguments.a_sync or not arguments.sync
        self.sync = arguments.sync

        # Limit on the number of passwords to try to login with.
        self.limit = arguments.limit
        self.test = arguments.test

        self.proxysleep = None
        if arguments.proxysleep:
            self.proxysleep = arguments.proxysleep

        self.password = arguments.password
        if self.test and not self.password:
            raise exceptions.FatalException(
                "Must provide password if in test mode."
            )

        self.user = User(arguments.username, password=arguments.password)


async def proxy_broker(proxies, loop):
    broker = Broker(proxies, timeout=6, max_conn=50, max_tries=1)
    while True:
        try:
            await broker.find(types=['HTTP'])
        # Proxy Broker will get hung up on tasks as we are trying to shut down
        # if we do not do this.
        except RuntimeError:
            break


def main(config):

    proxies = asyncio.Queue()
    passwords = asyncio.Queue()
    attempts = asyncio.Queue()
    results = asyncio.Queue()

    loop = asyncio.get_event_loop()
    engine = Engine(config, proxies)

    for s in SIGNALS:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(
                engine.shutdown(loop, attempts, signal=s, log=log)
            )
        )

    try:
        loop.run_until_complete(asyncio.gather(*[
            proxy_broker(proxies, loop),
            engine.run(loop, passwords, attempts, results)
        ]))

        engine.shutdown(loop, attempts, log=log)
    except KeyboardInterrupt:
        log.critical('Keyboard Interrupt')
        engine.shutdown(loop, attempts, force=True, log=log)
        loop.close()
    else:
        loop.close()


def get_args():
    args = ArgumentParser()
    args.add_argument('username', help='email or username')
    args.add_argument('-p', '--password', default=None)
    args.add_argument('-sleep', '--proxysleep', default=None, type=validate_proxy_sleep)
    args.add_argument('-sync', '--sync', dest='sync', action='store_true')
    args.add_argument('-async', '--async', dest='a_sync', action='store_true')
    args.add_argument('-test', '--test', dest='test', action='store_true')
    args.add_argument('-level', '--level', default='INFO', type=validate_log_level)
    args.add_argument('-limit', '--limit', default=None, type=validate_limit)
    return args.parse_args()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    arguments = get_args()
    os.environ['INSTAGRAM_LEVEL'] = arguments.level
    config = Configuration(arguments)

    with create_handlers(arguments):
        main(config)
