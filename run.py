from __future__ import absolute_import

import os
from platform import python_version
import signal
import logging

import asyncio

from app.engine import Engine
from app.proxies import proxy_broker, start_server
from app.logging import AppLogger, create_handlers
from app.config import get_config


# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = AppLogger(__file__)


def main(config):

    proxies = asyncio.Queue()
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
        broker, get_broker = start_server(loop)
        loop.run_until_complete(engine.run(loop, attempts, results))
        loop.run_until_complete(engine.shutdown(loop, attempts, forced=False))
    except KeyboardInterrupt:
        log.critical('Keyboard Interrupt')
        loop.run_until_complete(engine.shutdown(loop, attempts, forced=True))
        broker.stop()
        get_broker.stop()
        loop.close()
    else:
        broker.stop()
        get_broker.stop()
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
