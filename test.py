from __future__ import absolute_import

import os
import logging
import sys

import asyncio
import concurrent.futures

from app import settings
from app import exceptions
from app.lib.api import ProxyApi, InstagramSession


def get_token_for_proxy(proxy):

    log = logging.getLogger('get_token_for_proxy({})'.format(proxy.ip))
    log.info('running')

    session = InstagramSession(proxy=proxy)
    try:
        return session.get_token()
    except exceptions.ApiBadProxyException:
        log.info('Bad Proxy...')
        return None


async def run_token_tasks(executor, loop):

    log = logging.getLogger('run_token_tasks')
    log.info('Retrieving Tokens...')

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = list(proxy_api.get_proxies())[:10]

    log.info('Creating Executor Tasks...')
    loop = asyncio.get_event_loop()
    token_tasks = [
        loop.run_in_executor(executor, get_token_for_proxy, proxy)
        for proxy in proxies
    ]

    log.info('Waiting for Executor Tasks...')
    completed, pending = await asyncio.wait(token_tasks,
        return_when=asyncio.FIRST_COMPLETED)

    [task.cancel() for task in token_tasks]
    tokens = []
    tokens = [task.result() for task in completed]
    tokens = [token for token in tokens if token is not None]
    if len(tokens) != 0:
        log.info(f"Found token: {tokens[0]}!")
        await loop.shutdown_asyncgens()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

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
            run_token_tasks(executor, event_loop)
        )
    finally:
        event_loop.close()
