from __future__ import absolute_import

import os
from platform import python_version

import asyncio
from argparse import ArgumentParser

from app.engine import EngineAsync


def get_args():
    args = ArgumentParser()
    args.add_argument('username',
        help='email or username')
    return args.parse_args()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    arugments = get_args()

    loop = asyncio.get_event_loop()
    e = EngineAsync(arugments.username)
    try:
        loop.run_until_complete(e.attack(loop))
    finally:
        loop.close()
