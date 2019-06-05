# -*- coding: utf-8 -*-
import functools

from instattack.lib.utils import humanize_list


def allow_exception_input(func):
    @functools.wraps(allow_exception_input)
    def wrapped(instance, exc, **kwargs):
        if isinstance(exc, Exception):
            return func(instance, exc.__subtype__, **kwargs)
        else:
            return func(instance, exc, **kwargs)
    return wrapped


class DerivedMetrics(object):

    def _history(self, active=False):
        if active:
            return self.active_history
        return self.history

    def requests(self, *args, active=False, success=False, fail=False):
        index = args[0] if len(args) == 1 else None
        requests = self._history(active=active)
        if success:
            requests = [request for request in requests if request.confirmed]
        elif fail:
            requests = [request for request in requests if not request.confirmed]
        if index:
            try:
                return requests[index]
            except IndexError:
                return None
        return requests

    def num_requests(self, active=False, success=False, fail=False):
        return len(self.requests(active=active, success=success, fail=fail))

    @property
    def active_error_rate(self):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        return self.error_rate(active=True)

    @property
    def historical_error_rate(self):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        return self.error_rate(active=False)

    def errors(self, *args, active=False):
        if len(args) != 0:
            errors = []
            for err in args:
                errs = [
                    data for data in self._history(active=active)
                    if data.error == err
                ]
                errors.extend(errs)
            return errors
        else:
            return [
                data for data in self._history(active=active)
                if data.error is not None
            ]

    def num_errors(self, *args, active=False):
        return len(self.errors(*args, active=active))

    @property
    def confirmed(self):
        return self.num_requests(active=False, success=True) != 0

    @allow_exception_input
    def timeout_start(self, err):
        return self._timeouts[err]['start']

    @allow_exception_input
    def timeout_max(self, err):
        return self._timeouts[err]['max']

    @allow_exception_input
    def timeout_coefficient(self, err):
        return self._timeouts[err]['coefficient']

    @allow_exception_input
    def timeout_count(self, err):
        return self._timeouts[err]['count']

    @allow_exception_input
    def timeout_increment(self, err, count=None):
        """
        Right now, we will keep things simple and just use linear increments
        of the timeout.

        We need to make sure that this isn't exceeding towards infinity and
        reset it before then, moving the proxy out of hold.

        When using the exponentially increasing timeout style, we had the
        following:
        >>> count = count or self.timeout_count(err)
        >>> return (self.timeout_start(err) *
        >>>     math.exp(self.timeout_coefficient(err) * count))

        [x] TODO:
        --------
        Explore exponentially decaying increments, which might be more appropriate.
        """
        return self._timeouts[err]['increment']

    @allow_exception_input
    def timeout(self, err):
        return int(sum([
            self.timeout_increment(err, count=i)
            for i in range(self.timeout_count(err) + 1)
        ]))


class HumanizedMetrics(object):

    @property
    def humanized_active_errors(self):
        if self.num_errors(active=True) == 0:
            return "None"
        active_errors = self.errors(active=True)
        string_errors = humanize_list(active_errors)
        return string_errors

    @property
    def humanized_error_count(self):
        num_errors = self.num_errors()
        num_active_errors = self.num_errors(active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def humanized_connection_error_count(self):
        num_errors = self.num_errors('connection')
        num_active_errors = self.num_errors('connection', active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def humanized_response_error_count(self):
        num_errors = self.num_errors('response')
        num_active_errors = self.num_errors('response', active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def humanized_ssl_error_count(self):
        num_errors = self.num_errors('ssl')
        num_active_errors = self.num_errors('ssl', active=True)
        return f"{num_errors} (Active: {num_active_errors})"

    @property
    def num_active_successful_requests(self):
        return self.num_requests(active=True, success=True)

    @property
    def num_active_failed_requests(self):
        return self.num_requests(active=True, fail=True)

    @property
    def num_successful_requests(self):
        return self.num_requests(success=True)

    @property
    def num_failed_requests(self):
        return self.num_requests(fail=True)
