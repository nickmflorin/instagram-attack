from __future__ import absolute_import

import os
from platform import python_version

import asyncio
from argparse import ArgumentParser

from app.engine import EngineAsync


def get_args():
    args = ArgumentParser()
    args.add_argument('username', help='email or username')
    args.add_argument('-m', '--mode', default='async')
    args.add_argument('-p', '--password', default=None)
    args.add_argument('-test', '--test', dest='test', action='store_true')
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
    e = EngineAsync(arugments.username, mode=arugments.mode,
        test=arugments.test, password=arugments.password)
    try:
        loop.run_until_complete(e.attack(loop))
    finally:
        loop.close()
