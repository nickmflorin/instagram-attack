# -*- coding: utf-8 -*-
import aiohttp
from dataclasses import dataclass
from dacite import from_dict
from plumbum import colors
from typing import List, Any, Optional

from instattack.logger.constants import LoggingLevels
from instattack.src.login import constants
from instattack.src.proxies import Proxy
from instattack.src.base import TaskContext


__all__ = ('LoginContext', 'LoginAttemptContext', 'InstagramResult', )


@dataclass
class LoginContext(TaskContext):

    password: str
    index: int = 0

    @property
    def name(self):
        return f'Login Task'


@dataclass
class LoginAttemptContext(TaskContext):

    password: str
    proxy: Proxy
    index: int = 0
    parent_index: int = 0

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
    status: str = None
    user: Optional[bool] = None
    authenticated: Optional[bool] = None
    message: Optional[str] = None
    checkpoint_url: Optional[str] = None
    lock: Optional[bool] = False
    errors: InstagramResultErrors = InstagramResultErrors(error=[])
    error_type: Optional[str] = None
    showAccountRecoveryModal: Optional[bool] = False

    def __str__(self):
        string_rep = f"Authenticated: {self.authorized}"
        if self.authorized:
            return LoggingLevels.SUCCESS.message_formatter(string_rep)
        elif self.not_authorized:
            return LoggingLevels.ERROR.message_formatter(string_rep)
        else:
            string_rep = f"Authenticated: Inconclusive"
            return LoggingLevels.DEBUG.format(string_rep)

    @classmethod
    def from_dict(cls, data, context):
        data['context'] = context
        return from_dict(data_class=cls, data=data)

    @property
    def conclusive(self):
        # User will be `None` if checkpoint is required.
        return self.authorized or self.not_authorized

    @property
    def checkpoint_required(self):
        # We could more easily just check certain variables in the results but
        # it is safer to associate the entire set of variable values that
        # should be returned by the request with a state of the result.
        # Checkpoint URL is the only thing that would vary
        return self.message == constants.CHECKPOINT_REQUIRED

    @property
    def authorized(self):
        return self.authenticated or self.checkpoint_required

    @property
    def not_authorized(self):
        # We do not want to count the generic request error as not being
        # authorized, since this happens frequently for valid login attempts.
        return not self.authenticated and not self.has_generic_request_error

    @property
    def _errors(self):
        # Do not ask me why they framework their response errors as:
        # >>> {errors : {error: []}}
        return self.errors.error

    @property
    def error_message(self):
        """
        A present error_type should almost always correspond with error
        messages being in the array, but just in case we will do this because
        we cannot predict every response combination yet.
        """
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
        if self.errors == InstagramResultErrors(error=[constants.GENERIC_REQUEST_MESSAGE]):
            if self.error_type == constants.GENERIC_REQUEST_ERROR:
                return True
        return False
