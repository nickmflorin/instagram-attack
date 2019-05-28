#!/usr/bin/env python3
import argparse
import asyncio
import os

from instattack import logger
from instattack.conf import Configuration

from instattack.run import operator
from instattack.conf.utils import validate_log_level
from instattack.src.proxies.models import Proxy


SYNC = True


async def test_async(config):
    log = logger.get_async('Test Logger')
    proxy = Proxy(host="10.02.01.01", port=8124)
    await log.info('TEST INFO', extra={'password': 'test', 'proxy': proxy})


def test_sync(config):
    log = logger.get_sync('Test Logger')
    import site
    pcks = site.getsitepackages()
    print(pcks)


def main_async():
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

    loop.run_until_complete(test_async(config))
    loop.close()


def main_sync():
    parser = argparse.ArgumentParser()
    parser.add_argument('--level', default='INFO', type=validate_log_level, dest='level')
    parser.add_argument('--config', default='conf.yml', type=Configuration.validate, dest='config')

    args, unknown = parser.parse_known_args()

    loop = asyncio.get_event_loop()
    os.environ['LEVEL'] = args.level

    config = Configuration(path=args.config)

    oper = operator(config)
    oper.setup(loop)

    test_sync(config)
    loop.close()


if __name__ == '__main__':
    if SYNC:
        main_sync()
    else:
        main_async()
