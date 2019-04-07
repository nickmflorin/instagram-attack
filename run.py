from __future__ import absolute_import

import os
from platform import python_version
import signal
import logging

import asyncio
from argparse import ArgumentParser

from proxybroker import Broker

from app.engine import EngineAsync
from app.lib.users import User
from app.lib.logging import AppLogger

# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)


logging.setLoggerClass(AppLogger)

log = logging.getLogger(__file__).setLevel(logging.INFO)
logging.getLogger("proxybroker").setLevel(logging.CRITICAL)


async def proxy_broker(global_stop_event, proxies, loop):
    broker = Broker(proxies, timeout=6, max_conn=200, max_tries=1)
    while not global_stop_event.is_set():
        await broker.find(types=['HTTP'])


async def engine_runner(user, global_stop_event, proxies, loop, **kwargs):
    engine = EngineAsync(
        user,
        global_stop_event,
        proxies,
        **kwargs
    )

    while not global_stop_event.is_set():
        await engine.run(loop)


def main(arguments):

    global_stop_event = asyncio.Event()
    proxies = asyncio.Queue()
    user = User(arguments.username, password=arguments.password)

    loop = asyncio.get_event_loop()

    for s in SIGNALS:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(shutdown(loop, signal=s)))

    mode = 'sync' if arguments.sync else 'async'

    loop.run_until_complete(asyncio.gather(*[
        proxy_broker(global_stop_event, proxies, loop),
        engine_runner(user, global_stop_event, proxies, loop,
            mode=mode, test=arguments.test)
    ]))
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
    args.add_argument('-sync', '--sync', dest='sync', action='store_true')
    args.add_argument('-test', '--test', dest='test', action='store_true')
    return args.parse_args()


if __name__ == '__main__':

    arguments = get_args()

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    main(arguments)
