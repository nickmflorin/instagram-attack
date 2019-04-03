# -*- coding: utf-8 -*-
from __future__ import absolute_import

import aiohttp
from dacite import from_dict
from dataclasses import dataclass
from typing import List, Optional
import json

from app import settings
from app.lib import exceptions
from app.lib.logging import Styles


__all__ = ('InstagramResult', 'Proxy', )


@dataclass
class Proxy:

    ip: str
    port: int
    country: str

    def url(self, scheme="http"):
        return f"{scheme}://{self.ip}:{self.port}/"

    @property
    def address(self):
        return f'{self.ip}:{self.port}'

    @classmethod
    def from_text_file(cls, proxy_string):
        parts = proxy_string.split(' ')
        return Proxy(
            ip=parts[0].split(':')[0],
            port=int(parts[0].split(':')[1]),
            country=parts[1].split('-')[0]
        )

    @classmethod
    def from_scraped_tr(cls, row):
        td = row.find_all('td')
        if 'transparent' not in (td[4].string, td[5].string):
            return Proxy(
                ip=td[0].string,
                port=td[1].string,
                country=td[3].string
            )


@dataclass
class InstagramResultErrors:

    error: List[str]

    @property
    def message(self):
        if len(self.error) != 0:
            return self.error[0]


@dataclass
class InstagramResult:

    status: str
    user: Optional[bool]
    authenticated: Optional[bool]
    message: Optional[str]
    checkpoint_url: Optional[str] = None
    lock: Optional[bool] = False
    errors: InstagramResultErrors = None
    error_type: Optional[str] = None
    showAccountRecoveryModal: Optional[bool] = False

    def __str__(self):
        string_rep = f"Authenticated: {self.accessed}"
        if self.accessed:
            return Styles.GREEN.encode(string_rep)
        return Styles.RED.encode(string_rep)

    @classmethod
    def from_dict(cls, data):
        return from_dict(data_class=cls, data=data)

    @property
    def accessed(self):
        return self.authenticated or self.message == settings.CHECKPOINT_REQUIRED

    @property
    def invalid_user(self):
        return self.user is not None and not self.user

    @property
    def error_message(self):
        if self.errors:
            return self.errors.message

    @property
    def has_error(self):
        return self.error_type is not None
