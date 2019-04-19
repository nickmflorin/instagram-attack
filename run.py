from __future__ import absolute_import

import os
from platform import python_version
import signal
import logging

import asyncio

from app.engine import Engine
from app.server import TokenBroker, LoginBroker
from app.logging import AppLogger, create_handlers
from app.config import get_config
from proxybroker import ProxyPool


# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = AppLogger(__file__)


def main(config):

    attempts = asyncio.Queue()
    results = asyncio.Queue()

    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    proxy_pool = ProxyPool(proxies)

    engine = Engine(config)

    get_server = TokenBroker(proxies, loop=loop)
    post_server = LoginBroker(proxies, loop=loop)

    for s in SIGNALS:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(
                engine.shutdown(loop, attempts, signal=s, log=log)
            )
        )

    try:
        loop.run_until_complete(asyncio.gather(
            get_server.find(),  # TODO: Add a limit, we only need a few of these
            post_server.find(),
            engine.run(loop, proxy_pool, attempts, results, get_server)
        ))

        loop.run_until_complete(engine.shutdown(
            loop,
            attempts,
        ))

    except Exception as e:
        log.exception(e)
        loop.run_until_complete(engine.shutdown(
            loop,
            attempts,
        ))

    finally:
        loop.close()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    config = get_config()
    with create_handlers(config):
        main(config)
