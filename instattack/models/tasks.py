# -*- coding: utf-8 -*-
from dataclasses import dataclass

import aiohttp

from .proxies import RequestProxy


@dataclass
class TaskContext:

    def log_context(self, **kwargs):
        data = self.__dict__.copy()
        data['task'] = self.name
        data.update(**kwargs)
        return data


@dataclass
class TokenContext(TaskContext):

    proxy: RequestProxy
    index: int = 0

    @property
    def context_id(self):
        return 'token'

    @property
    def name(self):
        return f'Token Task - Attempt {self.index}'


@dataclass
class LoginContext(TaskContext):

    password: str
    token: str
    index: int = 0

    @property
    def context_id(self):
        return 'login'

    @property
    def name(self):
        return f'Login Task'


@dataclass
class LoginAttemptContext(TaskContext):

    password: str
    token: str
    proxy: RequestProxy
    index: int = 0
    parent_index: int = 0

    @property
    def context_id(self):
        return 'attempt'

    @property
    def name(self):
        return f'Login Task {self.parent_index} - Attempt {self.index}'
