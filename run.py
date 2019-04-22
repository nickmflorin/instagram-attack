from __future__ import absolute_import

import os
from platform import python_version
import logging
import signal
import sys

import asyncio
from proxybroker import ProxyPool

from app.server import TokenBroker, LoginBroker
from app.logging import AppLogger, log_handling
from app.config import get_config
from app.handlers import (
    proxy_handler, token_handler, results_handler, password_handler)
from app.lib.utils import cancel_remaining_tasks, handle_global_exception


# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = AppLogger(__file__)


async def shutdown(loop, get_server, post_server, signal=None):

    if signal:
        log.warning(f'Received exit signal {signal.name}...')
    log.info("Shutting Down...")

    # These might have already been stopped but just in case.
    # TODO: See if there is a way to check if they are still running and only
    # optionally log messages.
    log.info('Shutting Down Proxy Servers...')
    get_server.stop()
    post_server.stop()
    log.debug('Done Shutting Down Proxy Servers.')

    log.info('Cancelling Remaining Tasks...')
    await cancel_remaining_tasks()
    log.debug('Done Cancelling Remaining Tasks.')

    loop.stop()
    log.info('Shutdown Complete')


def attach_signals(loop, get_server, post_server, engine=None):
    for s in SIGNALS:
        loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(
                shutdown(loop, get_server, post_server, engine=engine, signal=s)
            )
        )


def main(loop, config, get_proxy_pool, post_proxy_pool, get_server, post_server):

    attempts = asyncio.Queue()
    results = asyncio.Queue()

    handle_get_proxy = proxy_handler(get_proxy_pool, config, results, attempts,
        method='GET')
    handle_post_proxy = proxy_handler(post_proxy_pool, config, results, attempts,
        method='POST')
    handle_token = token_handler(handle_get_proxy, config, results, attempts)

    handle_results = results_handler(config, results, attempts)
    handle_passwords = password_handler(handle_post_proxy, config, results, attempts)

    stop_event = asyncio.Event()

    try:
        log.info('Prepopulating GET Proxy Consumer...')
        loop.run_until_complete(handle_get_proxy.produce())
        log.debug('Done Prepopulating GET Proxy Consumer.')

        log.info('Starting GET Proxy Consumers...')

        results = loop.run_until_complete(asyncio.gather(
            handle_token.consume(loop, stop_event),
            handle_get_proxy.consume(loop, stop_event),
            get_server.find(),
        ))

    except Exception as e:
        handle_global_exception(e, exc_info=sys.exc_info())

    else:
        log.info('Stopped GET Proxy Consumer.')
        os.system('cls' if os.name == 'nt' else 'clear')

        token = results[0]
        log.notice('TOKEN : %s' % token)

        get_server.stop()

        try:
            log.info('Prepopulating POST Proxy Producers...')
            loop.run_until_complete(asyncio.gather(
                handle_passwords.produce(loop),
                handle_post_proxy.produce()
            ))
            log.debug('Done Prepopulating POST Proxy Producers.')

        except Exception as e:
            handle_global_exception(e, exc_info=sys.exc_info())
        else:
            log.info('Stopped Password Producer.')
            stop_event = asyncio.Event()

            try:
                log.info('Starting POST Proxy Consumer...')

                results = loop.run_until_complete(asyncio.gather(
                    handle_results.consume(loop, stop_event),
                    handle_passwords.consume(loop, stop_event, token),
                    handle_post_proxy.consume(loop, stop_event),
                    post_server.find(),
                ))

            except Exception as e:
                log.info('Starting to Dump Password Attempts...')
                loop.run_until_complete(handle_results.dump())
                log.debug('Password Attempts Dumped.')

                handle_global_exception(e, exc_info=sys.exc_info())

            else:
                log.debug('Stopped POST Proxy Consumer.')
                result = results[0]

                # TODO: Do this in a more obvious way.
                if result:
                    log.notice(f'Authenticated User!', extra={
                        'password': result.context.password
                    })

            finally:
                log.info('Starting to Dump Password Attempts...')
                loop.run_until_complete(handle_results.dump())
                log.debug('Password Attempts Dumped.')


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    sys.stdout.write("\x1b[2J\x1b[H")

    # Make max_error_rate and max_resp_time for proxies configurable, and if
    # they are set, than we can filter the proxies we read by those values.
    config = get_config()
    with log_handling(config=config):
        # os.system('cls' if os.name == 'nt' else 'clear')
        loop = asyncio.get_event_loop()

        # TODO: Can we move this initialization to the proxy_handler object?
        get_proxies = asyncio.Queue()
        post_proxies = asyncio.Queue()

        get_server = TokenBroker(get_proxies)
        post_server = LoginBroker(post_proxies)

        get_proxy_pool = ProxyPool(get_proxies)
        post_proxy_pool = ProxyPool(post_proxies)

        try:
            main(
                loop,
                config,
                get_proxy_pool,
                post_proxy_pool,
                get_server,
                post_server
            )

        # This would likely be exceptions from the proxybroker package since
        # our other exceptions are handled in main().
        except Exception as e:
            handle_global_exception(e, exc_info=sys.exc_info())

        finally:
            loop.run_until_complete(
                shutdown(loop, get_server, post_server))
            loop.close()
