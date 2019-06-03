# -*- coding: utf-8 -*-
from instattack.lib.utils import humanize_list


class HumanizedMetrics(object):

    @property
    def humanized_active_errors(self):
        if len(self.active_errors) == 0:
            return "No Active Errors"

        errors = self.active_errors.keys()
        string_errors = []
        for err in errors:
            string_errors.append(err.__subtype__)
        string_errors = humanize_list(errors)
        return f"Active Errors: {string_errors}"

    @property
    def humanized_error_count(self):
        num_errors = self._num_errors()
        num_active_errors = self._num_errors(active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def humanized_connection_error_count(self):
        num_errors = self._num_errors('connection')
        num_active_errors = self._num_errors('connection', active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def humanized_response_error_count(self):
        num_errors = self._num_errors('response')
        num_active_errors = self._num_errors('response', active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def humanized_ssl_error_count(self):
        num_errors = self._num_errors('ssl')
        num_active_errors = self._num_errors('ssl', active=True)
        return f"{num_errors} (Active: {num_active_errors})"
