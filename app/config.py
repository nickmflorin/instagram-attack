from __future__ import absolute_import

from argparse import ArgumentParser

from dacite import from_dict
from dataclasses import dataclass, field
from typing import List, Optional

from app.lib.users import User
from app.lib.utils import validate_int, validate_log_level


@dataclass
class Config:

    username: str
    user: object = field(init=False)

    proxy_sleep: int = 0
    fetch_time: int = 8
    max_retries: int = 0
    password_limit: int = 0
    connection_limit: int = 100
    token_attempt_limit: int = 5
    connector_timeout: int = 3
    batch_size: int = 100
    level: str = 'INFO'

    def __post_init__(self):
        self.user = User(self.username)

    @classmethod
    def from_args(cls, arguments):
        return cls(
            username=arguments.username,
            proxy_sleep=arguments.proxy_sleep,
            max_retries=arguments.max_retries,
            connection_limit=arguments.connection_limit,
            password_limit=arguments.pwlimit,
            token_attempt_limit=arguments.tokenlimit,
            connector_timeout=arguments.connector_timeout,
            batch_size=arguments.batch_size,
            level=arguments.level
        )


def get_config():
    args = ArgumentParser()
    args.add_argument('username', help='email or username')

    args.add_argument('-sleep', '--proxy_sleep', default=None, type=validate_int,
        help=(
            ""
        )
    )
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
