# -*- coding: utf-8 -*-
import aiohttp
from dataclasses import dataclass

from instattack.core.models import TaskContext
from instattack.core.proxies import Proxy


@dataclass
class TokenContext(TaskContext):

    proxy: Proxy
    index: int = 0

    @property
    def context_id(self):
        return 'token'

    @property
    def name(self):
        return f'Token Task - Attempt {self.index}'
