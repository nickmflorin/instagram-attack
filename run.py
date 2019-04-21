from __future__ import absolute_import

import os
from platform import python_version
import logging
import signal

import asyncio
from proxybroker import ProxyPool

from app.engine import Engine
from app.server import TokenBroker, LoginBroker
from app.logging import AppLogger, create_handlers
from app.config import get_config
from app.handlers import proxy_handler, token_handler
from app.lib.utils import cancel_remaining_tasks, handle_global_exception


# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = AppLogger(__file__)


def attach_signals(loop, engine):
    for s in SIGNALS:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(
                engine.shutdown(loop, signal=s)
            )
        )


def test():
    e = Exception("BLAH")
    raise e


def main(loop, config, get_proxy_pool, post_proxy_pool, get_server, post_server):

    attempts = asyncio.Queue()
    results = asyncio.Queue()

    get_proxy_handler = proxy_handler(get_proxy_pool, config, results, attempts)
    post_proxy_handler = proxy_handler(post_proxy_pool, config, results, attempts)
    toke_handler = token_handler(get_proxy_handler, config, results, attempts)

    engine = Engine(config, get_proxy_handler, post_proxy_handler, attempts, results)
    attach_signals(loop, engine)

    import traceback
    import sys
    try:
        test()
    except Exception as e:
        handle_global_exception(e, exc_info=sys.exc_info())
        exc_type, exc_value, exc_traceback = sys.exc_info()

    return
    try:
        stop_event = asyncio.Event()
        results = loop.run_until_complete(asyncio.gather(
            toke_handler.consume(loop, stop_event),
            get_proxy_handler.consume(loop, stop_event),
            get_server.find(),
        ))

        token = results[0]
        log.notice('TOKEN : %s' % token)
        # loop.run_until_complete(asyncio.gather(
        #     engine.run(loop, token),
        #     post_proxy_handler.consume(loop),
        # ))

    except Exception as e:
        log.exception(e)

    finally:
        loop.run_until_complete(engine.shutdown(loop))


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    config = get_config()
    with create_handlers(config):

        loop = asyncio.get_event_loop()

        get_proxies = asyncio.Queue()
        post_proxies = asyncio.Queue()

        get_server = TokenBroker(get_proxies)
        post_server = LoginBroker(post_proxies)

        get_proxy_pool = ProxyPool(get_proxies)
        post_proxy_pool = ProxyPool(post_proxies)

        try:
            # loop.run_until_complete(asyncio.gather(
            main(loop, config, get_proxy_pool, post_proxy_pool, get_server,
                post_server),
                # get_server.find(),
                # post_server.find())
            # ))

        # This would likely be exceptions from the proxybroker package since
        # our other exceptions are handled in main().
        except Exception as e:
            log.exception(e)

        finally:
            get_server.stop()  # Just in case not stopped yet.
            post_server.stop()
            loop.stop()
            loop.close()
