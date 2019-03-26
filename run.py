from __future__ import absolute_import

import os
from platform import python_version

from app import settings
from argparse import ArgumentParser

from app.engine import Engine
from app.validation import validate_mode, validate_password_file


def get_args():
    args = ArgumentParser()
    args.add_argument('username',
        help='email or username')
    args.add_argument('passlist',
        type=validate_password_file,
        help='List of passwords')
    args.add_argument('-nc', '--no-color',
        dest='color',
        action='store_true',
        help='disable colors')
    args.add_argument('-m', '--mode',
        default=2,
        type=validate_mode,
        help='modes: 0 => 32 bots; 1 => 16 bots; 2 => 8 bots; 3 => 4 bots')
    return args.parse_args()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if int(python_version()[0]) < 3:
        print('[!] Please use Python 3')
        exit()

    arugments = get_args()

    engine = Engine(
        arugments.username,
        settings.MODES[arugments.mode],
        arugments.passlist,
        is_color=True if not arugments.color else False,
    )
    engine.start()
