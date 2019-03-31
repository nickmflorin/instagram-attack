from __future__ import absolute_import

import os
from platform import python_version

import asyncio
from argparse import ArgumentParser

from app.engine import EngineAsync, EngineSync


def get_args():
    args = ArgumentParser()
    args.add_argument('username',
        help='email or username')
    args.add_argument('-sync', '--sync',
        dest='sync',
        action='store_true',
        help='Test attack synchronously.')
    return args.parse_args()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    arugments = get_args()

    if not arugments.sync:
        event_loop = asyncio.get_event_loop()
        e = EngineAsync(arugments.username, event_loop)
        e.run()
    else:
        e = EngineSync(arugments.username)
        e.run()


# VISIT https://realpython.com/python-concurrency/

# We should probably start trying to move towards this.
# import asyncio
# import time
# import aiohttp


# async def download_site(session, url):
#     async with session.get(url) as response:
#         print("Read {0} from {1}".format(response.content_length, url))


# async def download_all_sites(sites):
#     async with aiohttp.ClientSession() as session:
#         tasks = []
#         for url in sites:
#             task = asyncio.ensure_future(download_site(session, url))
#             tasks.append(task)
#         await asyncio.gather(*tasks, return_exceptions=True)


# if __name__ == "__main__":
#     sites = [
#         "https://www.jython.org",
#         "http://olympus.realpython.org/dice",
#     ] * 80
#     start_time = time.time()
#     asyncio.get_event_loop().run_until_complete(download_all_sites(sites))
#     duration = time.time() - start_time
#     print(f"Downloaded {len(sites)} sites in {duration} seconds")
