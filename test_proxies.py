from __future__ import absolute_import

import os
import sys

from platform import python_version
import logbook

import asyncio

from app.proxies import test_proxies, proxy_broker


# logging.getLogger("proxybroker").setLevel(logging.CRITICAL)
log = logbook.Logger(__file__)


def main():

    proxies = asyncio.Queue()
    loop = asyncio.get_event_loop()

    loop.run_until_complete(asyncio.gather(*[
        asyncio.ensure_future(proxy_broker(proxies, loop)),
        asyncio.ensure_future(test_proxies(proxies, loop)),
    ]))

    loop.close()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        sys.exit()

    base_handler = logbook.StreamHandler(sys.stdout, level="INFO", bubble=True)
    with base_handler:
        main()
