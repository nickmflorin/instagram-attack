from __future__ import absolute_import

from dacite import from_dict
from dataclasses import dataclass, field
from typing import List, Optional

from instattack.users.models import User


@dataclass
class Config:

    username: str
    user: object = field(init=False)

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
            max_retries=arguments.max_retries,
            connection_limit=arguments.connection_limit,
            password_limit=arguments.pwlimit,
            token_attempt_limit=arguments.tokenlimit,
            connector_timeout=arguments.connector_timeout,
            batch_size=arguments.batch_size,
            level=arguments.level
        )
