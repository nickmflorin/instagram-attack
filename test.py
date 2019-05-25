#!/usr/bin/env python3
import argparse
import asyncio
import os

from instattack import logger
from instattack.src import operator

from instattack.src.config import Configuration
from instattack.src.utils import validate_log_level


async def test(config):
    log = logger.get_async('Test Logger')
    queue = asyncio.PriorityQueue()

    await queue.put(((1, 2), 'First'))
    await queue.put(((3, 4), 'Third'))
    await queue.put(((2, 1), 'Second'))

    retrieved = await queue.get()
    await log.success(retrieved)

    await queue.put(((1, 1), 'New First'))
    await queue.put(((2, 2), 'New Second'))
    await queue.put(((6, 1), 'Last'))

    retrieved = await queue.get()
    print(retrieved)

    retrieved = await queue.get()
    print(retrieved)

    retrieved = await queue.get()
    print(retrieved)


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
