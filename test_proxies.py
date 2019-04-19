from __future__ import absolute_import

import os
import sys

from platform import python_version

import aiohttp
import asyncio

from app import settings
from app.server import TokenBroker, LoginBroker
from app.logging import base_handler
from app.logging import AppLogger


log = AppLogger(__file__)


async def make_post_request(session, **params):
    async with session.post(
        settings.TEST_POST_REQUEST_URL,
        proxy=settings.POST_URL,
        json=params,
        headers={'Content-Type': 'application/json'},
    ) as response:
        return await response.json()


async def make_get_request(session, **params):
    try:
        async with session.get(
            settings.TEST_GET_REQUEST_URL,
            proxy=settings.GET_URL,
            json=params,
            headers={'Content-Type': 'application/json'},
        ) as response:
            return await response.json()
    except Exception as e:
        log.error(e.__class__.__name__)
        return


async def main(loop, get_server, post_server):

    connector = aiohttp.TCPConnector(ssl=False, enable_cleanup_closed=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            log.notice('Making GET Request')
            try:
                resp = await make_get_request(session, foo='bar', bat='baz')
            except Exception as e:
                log.error(e.__class__.__name__)
            else:
                break

        print('Results %s' % resp['args'])
        get_server.stop()

        while True:
            log.notice('Making POST Request')
            try:
                resp = await make_post_request(session, foo='bar', bat='baz')
            except Exception as e:
                log.error(e.__class__.__name__)
            else:
                break

        print('Results %s' % resp['json'])


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        sys.exit()

    with base_handler:

        loop = asyncio.get_event_loop()

        get_server = TokenBroker(loop=loop)
        post_server = LoginBroker(loop=loop)

        get_server.serve()
        post_server.serve()

        loop.run_until_complete(main(loop, get_server, post_server))

        post_server.stop()

        loop.stop()
        loop.close()
