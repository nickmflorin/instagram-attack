#!/usr/bin/env python3
import argparse
import asyncio
import os

from instattack import logger
from instattack.exceptions import HttpServerConnectionError
from instattack.conf import Configuration

from instattack.src import operator
from instattack.conf.utils import validate_log_level


async def test(config):
    log = logger.get_async('Test Logger')

    e = HttpServerConnectionError()
    await log.error(e)


def main():
    # We have to retrieve the --level at the top level and then use it to set
    # the environment variable - which is in turn used to configure the loggers.
    parser = argparse.ArgumentParser()
    parser.add_argument('--level', default='INFO', type=validate_log_level, dest='level')
    parser.add_argument('--config', default='conf.yml', type=Configuration.validate, dest='config')

    args, unknown = parser.parse_known_args()

    loop = asyncio.get_event_loop()
    os.environ['LEVEL'] = args.level

    config = Configuration(path=args.config)

    oper = operator(config)
    oper.setup(loop)

    loop.run_until_complete(test(config))
    loop.close()


if __name__ == '__main__':
    main()
