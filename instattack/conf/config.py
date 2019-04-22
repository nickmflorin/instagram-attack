from __future__ import absolute_import

from argparse import ArgumentParser

from .models import Config
from .utils import validate_int, validate_log_level


def get_config():
    args = ArgumentParser()
    args.add_argument('username', help='email or username')

    args.add_argument('-bs', '--batch_size', default=100, type=validate_int,
        help=(
            "BATCH_SIZE"
        )
    )
    args.add_argument('-ft', '--fetch_time', default=8, type=validate_int,
        help=(
            "FETCH_TIME"
        )
    )
    args.add_argument('-connlimit', '--connection_limit', default=3, type=validate_int,
        help=(
            "CONNECTOR_CONNECTION_LIMIT"
        )
    )
    args.add_argument('-contimeout', '--connector_timeout', default=3, type=validate_int,
        help=(
            "CONNECTOR_KEEP_ALIVE_TIMEOUT"
        )
    )
    args.add_argument('-retry', '--max_retries', default=None,
        help=(
            "The number of allowable retries when there are connection errors "
            "associated with the client or proxy."
        )
    )
    args.add_argument('-level', '--level', default='INFO', type=validate_log_level,
        help=(
            ""
        )
    )
    args.add_argument('-plim', '--pwlimit', default=None, type=validate_int,
        help=(
            "The number of password attempts to limit the brute force attack to. "
            "If not specified, uses all of the generated passwords."
        )
    )
    args.add_argument('-tlim', '--tokenlimit', default=5, type=validate_int,
        help=(
            "TOKEN_ATTEMPT_LIMIT"
        )
    )
    arguments = args.parse_args()
    return Config.from_args(arguments)
