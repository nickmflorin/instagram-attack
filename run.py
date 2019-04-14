from __future__ import absolute_import

import os
from platform import python_version
import signal
import logging
import sys

import asyncio
from argparse import ArgumentParser

from proxybroker import Broker
import logbook

from app.engine import Engine
from app.lib import exceptions
from app.lib.logging import APP_FORMAT
from app.lib.users import User
from app.lib.utils import validate_proxy_sleep, validate_log_level, validate_limit

# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = logbook.Logger(__file__)


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


async def proxy_broker(global_stop_event, proxies, loop):
    broker = Broker(proxies, timeout=6, max_conn=50, max_tries=1)
    while not global_stop_event.is_set():
        try:
            await broker.find(types=['HTTP'])
        # Proxy Broker will get hung up on tasks as we are trying to shut down
        # if we do not do this.
        except RuntimeError:
            break


def main(config):

    global_stop_event = asyncio.Event()
    proxies = asyncio.Queue()

    loop = asyncio.get_event_loop()

    for s in SIGNALS:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(loop, signal=s)))

    engine = Engine(
        config,
        global_stop_event,
        proxies,
    )

    loop.run_until_complete(asyncio.gather(*[
        proxy_broker(global_stop_event, proxies, loop),
        engine.run(loop)
    ]))

    loop.run_until_complete(shutdown(loop))
    loop.close()


async def shutdown(loop, signal=None):
    if signal:
        log.info(f'Received exit signal {signal.name}...')

    tasks = [task for task in asyncio.Task.all_tasks() if task is not
         asyncio.tasks.Task.current_task()]

    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info('Finished awaiting cancelled tasks, results.')
    loop.stop()


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
    config = Configuration(arguments)

    log_handler = logbook.StreamHandler(sys.stdout, level=arguments.level)
    log_handler.format_string = APP_FORMAT
    log_handler.push_application()

    os.environ['INSTAGRAM_LEVEL'] = arguments.level

    main(config)
