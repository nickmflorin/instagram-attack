# -*- coding: utf-8 -*-
from __future__ import absolute_import

import aiohttp
from dacite import from_dict
from dataclasses import dataclass
from typing import List, Optional
import json

from app import settings
from app.lib import exceptions
from app.lib.logging.constants import Colors


__all__ = ('InstagramResult', )


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
            return Colors.GREEN.encode(string_rep)
        return Colors.RED.encode(string_rep)

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
