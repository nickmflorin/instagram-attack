# -*- coding: utf-8 -*-
from dataclasses import dataclass
from dacite import from_dict
import typing

from instattack import settings
from termx import settings as termx

from instattack.core.exceptions import InstattackError

from .proxies import Proxy


@dataclass
class InstagramResultErrors:

    error: typing.List[str]

    @property
    def message(self):
        try:
            return self.error[0]
        except IndexError:
            raise InstattackError("There are no errors.")


@dataclass
class InstagramResult:

    proxy: Proxy
    password: str

    status: str = None
    user: typing.Optional[bool] = None
    authenticated: typing.Optional[bool] = None
    message: typing.Optional[str] = None
    checkpoint_url: typing.Optional[str] = None
    lock: typing.Optional[bool] = False
    errors: InstagramResultErrors = InstagramResultErrors(error=[])
    error_type: typing.Optional[str] = None
    showAccountRecoveryModal: typing.Optional[bool] = False

    def __str__(self):
        string_rep = f"Authenticated: {self.authorized}"
        if self.authorized:
            return termx.Formats.SUCCESS(string_rep)
        elif self.not_authorized:
            return termx.Formats.ERROR(string_rep)
        else:
            string_rep = f"Authenticated: Inconclusive"
            return termx.Formats.NOTSET(string_rep)

    @classmethod
    def from_dict(cls, data, proxy=None, password=None):
        data['password'] = password
        data['proxy'] = proxy
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
        return self.message == settings.checkpoint_required

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
        if self.errors == InstagramResultErrors(error=[settings.generic_request_message]):
            if self.error_type == settings.generic_request_error:
                return True
        return False


@dataclass
class InstagramResults:

    results: typing.List[InstagramResult]

    @property
    def num_results(self):
        return len(self.results)

    @property
    def has_authenticated(self):
        return len([res for res in self.results if res.authorized]) != 0

    @property
    def authenticated_result(self):
        auth_results = [res for res in self.results if res.authorized]
        if len(auth_results) != 0:
            return auth_results[0]

    def add(self, result):
        self.results.append(result)
