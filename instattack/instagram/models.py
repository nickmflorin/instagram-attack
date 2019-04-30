# -*- coding: utf-8 -*-
from __future__ import absolute_import

from dacite import from_dict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import json

import aiohttp

from instattack import Colors, exceptions, settings
from instattack.proxies.models import RequestProxy


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


@dataclass
class InstagramResultErrors:

    error: List[str]

    @property
    def message(self):
        try:
            return self.error[0]
        except IndexError:
            raise exceptions.AppException("There are no errors.")


@dataclass
class InstagramResult:

    context: LoginAttemptContext
    status: str
    user: Optional[bool]
    authenticated: Optional[bool]
    message: Optional[str]
    checkpoint_url: Optional[str] = None
    lock: Optional[bool] = False
    errors: InstagramResultErrors = InstagramResultErrors(error=[])
    error_type: Optional[str] = None
    showAccountRecoveryModal: Optional[bool] = False

    def __str__(self):
        string_rep = f"Authenticated: {self.authorized}"
        if self.authorized:
            return Colors.GREEN.format(string_rep)
        return Colors.RED.format(string_rep)

    @classmethod
    def from_dict(cls, data, context):
        data['context'] = context
        return from_dict(data_class=cls, data=data)

    @property
    def conclusive(self):
        # User will be `None` if checkpoint is required.
        return self.authorized or self.not_authorized

    @property
    def checkpoint_required_state(self):
        return {
            'status': 'fail',
            'user': None,
            'authenticated': None,
            'message': settings.CHECKPOINT_REQUIRED,
            'lock': False,
            'errors': InstagramResultErrors(error=[]),
            'error_type': None,
            'showAccountRecoveryModal': False
        }

    @property
    def checkpoint_required(self):
        # We could more easily just check certain variables in the results but
        # it is safer to associate the entire set of variable values that
        # should be returned by the request with a state of the result.
        # Checkpoint URL is the only thing that would vary
        current_state = self.__dict__.copy()
        del current_state['context']
        if 'checkpoint_url' in current_state:
            del current_state['checkpoint_url']
        return current_state == self.checkpoint_required_state

    @property
    def authorized(self):
        return self.authenticated or self.checkpoint_required

    @property
    def not_authorized(self):
        # We do not want to count the generic request error as not being
        # authorized, since this happens frequently for valid login attempts.
        return not self.authenticated and not self.has_generic_request_error

    @property
    def invalid_user(self):
        return self.user is not None and not self.user

    @property
    def _errors(self):
        # Do not ask me why they framework their response errors as:
        # >>> {errors : {error: []}}
        return self.errors.error

    @property
    def error_message(self):
        # A present error_type should almost always correspond with error
        # messages being in the array, but just in case we will do this because
        # we cannot predict every response combination yet.
        if self.has_error:
            # Do not ask me why they framework their response errors as:
            # >>> {errors : {error: []}}
            if len(self._errors) != 0:
                return self.errors.message
            return self.error_type

    @property
    def has_error(self):
        return self.error_type is not None or len(self._errors) != 0

    @property
    def has_generic_request_error(self):
        state = {
            'status': 'ok',
            'user': None,
            'authenticated': None,
            'message': None,
            'checkpoint_url': None,
            'lock': False,
            'errors': InstagramResultErrors(
                error=[settings.GENERIC_REQUEST_MESSAGE]),
            'error_type': settings.GENERIC_REQUEST_ERROR,
            'showAccountRecoveryModal': False
        }
        return self.__dict__ == state
