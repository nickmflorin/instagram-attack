from __future__ import absolute_import

from argparse import ArgumentParser
import os
import sys
from urllib.parse import urlparse
from platform import python_version

import aiohttp
import asyncio

from proxybroker import ProxyPool

from instattack.utils import bar, cancel_remaining_tasks
from instattack.conf import settings
from instattack.conf.utils import validate_method

from instattack.logger import AppLogger, log_handling
from instattack.logger.utils import handle_global_exception

from instattack.proxies import BROKERS
from instattack.proxies.models import Proxy
from instattack.proxies.utils import read_proxies, write_proxies


log = AppLogger(__file__)


async def make_test_post_request(session, proxy, **params):
    async with session.post(
        settings.TEST_POST_REQUEST_URL,
        proxy=proxy.url(),
        json=params,
        headers={'Content-Type': 'application/json'},
    ) as response:
        return await response.json()


async def make_test_get_request(session, proxy, **params):
    async with session.get(
        settings.TEST_GET_REQUEST_URL,
        proxy=proxy.url(),
        json=params,
        headers={'Content-Type': 'application/json'},
    ) as response:
        return await response.json()


async def display_proxy(proxy):
    log.info('Proxy, Max Error Rate: %s, Avg Resp Time: %s' % (
        proxy.error_rate, proxy.avg_resp_time
    ))


async def collect_proxies_from_pool(pool, scheme, method='GET', limit=10,
        overwrite=False, max_resp_time=None, max_error_rate=None,
        show=False, save=False):

    collected = []

    current_proxies = []

    # Maybe we want to be able to test and show proxies that are not already
    # saved for us - by not checking save value?
    if not overwrite and save:
        current_proxies = read_proxies(method=method)

    progress = bar(label='Collecting', max_value=limit)
    progress.start()
    while len(collected) < limit:
        try:
            proxy = await pool.get(scheme=scheme)
        # Weird error from ProxyBroker that makes no sense...
        # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
        except TypeError as e:
            log.warning(e)
        else:
            if proxy not in current_proxies:
                if max_resp_time and proxy.avg_resp_time > max_resp_time:
                    continue
                if max_error_rate and proxy.error_rate > max_error_rate:
                    continue

                _proxy = Proxy(
                    avg_resp_time=proxy.avg_resp_time,
                    error_rate=proxy.error_rate,
                    host=proxy.host,
                    port=proxy.port
                )
                if show:
                    display_proxy(_proxy)

                collected.append(_proxy)
                progress.update()

    progress.finish()
    return collected


async def collect_proxies(loop, arguments):

    proxies = asyncio.Queue()
    server = BROKERS[arguments.method](proxies)
    pool = ProxyPool(proxies)

    scheme = urlparse(settings.URLS[arguments.method]).scheme

    log.notice(f'Spinning Up {args.method} Server')
    asyncio.create_task(server.find())

    collected = await collect_proxies_from_pool(
        pool,
        scheme,
        method=arguments.method,
        limit=arguments.limit,
        overwrite=arguments.clear,
        max_resp_time=arguments.max_resp_time,
        max_error_rate=arguments.max_error_rate,
        show=arguments.show,
    )

    if arguments.save:
        filename = settings.FILENAMES.PROXIES[arguments.method]
        log.info(f'Saving {len(collected)} Proxies to {filename}.')
        write_proxies(collected, method=arguments.method, overwrite=arguments.clear)


async def test_proxies(loop, arguments):
    test_reauests = {
        'GET': make_test_get_request,
        'POST': make_test_post_request,
    }

    proxies = read_proxies(method=arguments.method, limit=arguments.limit)
    req = test_reauests[arguments.method]

    connector = aiohttp.TCPConnector(
        ssl=False,
        enable_cleanup_closed=True
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        progress = bar(label='Making Requests', max_value=len(proxies))
        progress.start()
        for proxy in proxies:
            log.notice(f'Making {arguments.method} Request', extra={'proxy': proxy})
            try:
                resp = await req(session, proxy, foo='bar', bat='baz')
            except Exception as e:
                log.error(e.__class__.__name__)
                progress.update()
            else:
                progress.update()
                if arguments.method == 'GET':
                    log.notice(resp['arg'])
                else:
                    log.notice(resp['json'])


def get_args():

    def add_proxy_test_actions(parser, func=None):
        parser.add_argument('method', type=validate_method)
        parser.add_argument('--limit', default=1, type=int)
        parser.set_defaults(func=func)

    def add_proxy_retrieval_actions(parser, func=None, show=False, save=False):

        parser.add_argument('method', type=validate_method)
        parser.add_argument('--max_error_rate', default=None, type=float)
        parser.add_argument('--max_resp_time', default=None, type=float)
        parser.add_argument('--limit', default=10, type=int)
        parser.add_argument('--clear', action="store_true")
        parser.set_defaults(func=func, show=show, save=save)

    def split_proxy_parser(parser):

        parsers = parser.add_subparsers()

        collect_parser = parsers.add_parser('collect')
        add_proxy_retrieval_actions(collect_parser, func=collect_proxies, save=True)

        show_parser = parsers.add_parser('show')
        add_proxy_retrieval_actions(show_parser, func=collect_proxies, show=True)

        test_parser = parsers.add_parser('test')
        add_proxy_test_actions(test_parser, func=test_proxies)

    def split_parser(parser):

        parsers = parser.add_subparsers()

        proxy_parser = parsers.add_parser('proxies')
        split_proxy_parser(proxy_parser)

    parser = ArgumentParser()
    split_parser(parser)

    args = parser.parse_args()
    return args


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        sys.exit()

    args = get_args()

    with log_handling():
        loop = asyncio.get_event_loop()

        try:
            loop.run_until_complete(args.func(loop, args))

        except Exception as e:
            handle_global_exception(e, exc_info=sys.exc_info())

        finally:
            loop.run_until_complete(cancel_remaining_tasks())
            loop.stop()
            loop.close()
