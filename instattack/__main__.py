#!/usr/bin/env python3
import argparse
import asyncio
import os
import warnings


warnings.filterwarnings("ignore")


def main():
    from instattack.conf import Configuration
    from instattack.conf.utils import validate_log_level

    # We have to retrieve the --level at the top level and then use it to set
    # the environment variable - which is in turn used to configure the loggers.
    parser = argparse.ArgumentParser()
    parser.add_argument('--level', default='INFO', type=validate_log_level, dest='level')
    parser.add_argument('--config', default='conf.yml', type=Configuration.validate, dest='config')

    parsed, unknown = parser.parse_known_args()

    loop = asyncio.get_event_loop()

    os.environ['INSTATTACK_LOG_LEVEL'] = parsed.level.name

    config = Configuration(path=parsed.config)

    # Wait to import from src directory until LEVEL set in os.environ so that
    # loggers are all created with correct level.
    from .run import operator
    oper = operator(config)
    oper.start(loop, *unknown)
    loop.close()
