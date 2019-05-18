#!/usr/bin/env python3
import argparse
import asyncio

from instattack.conf.utils import validate_log_level
from .cli import start


def main():
    # We have to retrieve the --level at the top level and then use it to set
    # the environment variable - which is in turn used to configure the loggers.
    parser = argparse.ArgumentParser()
    parser.add_argument('--level', default='INFO', type=validate_log_level)
    args, unknown = parser.parse_known_args()

    loop = asyncio.get_event_loop()
    start(loop, args)
    loop.close()
