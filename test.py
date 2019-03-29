from __future__ import absolute_import

from argparse import ArgumentParser
import os
import queue
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app import settings
from app.exceptions import (ApiBadProxyException, ApiClientException,
    ApiTimeoutException, ApiMaxRetryError, ApiException, ApiSSLException)
from app.lib.users import User, Users
from app.lib.api import ProxyApi, InstagramApi, InstagramSession

import asyncio
import concurrent.futures
import logging
import sys
import time
import aiohttp
import app.settings as settings
import app.exceptions as exceptions
from app.lib.api import ProxyApi
import requests

def blocks(proxy):
    log = logging.getLogger('blocks({})'.format(proxy.url))
    log.info('running')
    # session = aiohttp.ClientSession(
    #     connector=aiohttp.TCPConnector(verify_ssl=False, limit=1)
    # )
    session = requests.Session()
    session.proxies.update(
        http=proxy.address,
        https=proxy.address
    )
    try:
        # response = session.get(settings.INSTAGRAM_URL, proxy=proxy.url())
        response = session.get(settings.INSTAGRAM_URL)
    except:
        log.info('response error')
        return None
    else:
        cookies = response.cookies.get_dict()
        if 'csrftoken' not in cookies:
            # raise exceptions.ApiBadProxyException(proxy=proxy)
            return None
        return cookies['csrftoken']
        # print(response.cookies['csrftoken'].value)
        # log.info('done')
        # return response.cookies['csrftoken'].value


async def run_token_tasks(executor):
    log = logging.getLogger('run_blocking_tasks')
    log.info('starting')

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = list(proxy_api.get_proxies())[:4]

    log.info('creating executor tasks')
    loop = asyncio.get_event_loop()
    blocking_tasks = [
        loop.run_in_executor(executor, blocks, proxy)
        for proxy in proxies
    ]
    log.info('waiting for executor tasks')
    completed, pending = await asyncio.wait(blocking_tasks)
    results = [t.result() for t in completed]
    print(results)
    log.info('results: {!r}'.format(results))

    log.info('exiting')


if __name__ == '__main__':
    # Configure logging to show the name of the thread
    # where the log message originates.
    logging.basicConfig(
        level=logging.INFO,
        format='%(threadName)10s %(name)18s: %(message)s',
        stream=sys.stderr,
    )

    # Create a limited thread pool.
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=3,
    )

    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(
            run_token_tasks(executor)
        )
    finally:
        event_loop.close()


def get_args():
    args = ArgumentParser()
    args.add_argument('method', help='Test method to run.')
    return args.parse_args()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    arugments = get_args()

    # Probably not the best way to do this, but we'll worry about that later.
    method = eval(arugments.method)
    method.__call__()
