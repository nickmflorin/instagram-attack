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
