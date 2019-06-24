# -*- coding: utf-8 -*-
import functools

from termx.ext.utils import humanize_list
from instattack import settings

from instattack.core.exceptions import ConfigError


def allow_exception_input(func):
    @functools.wraps(allow_exception_input)
    def wrapped(instance, exc, **kwargs):
        if isinstance(exc, Exception):
            return func(instance, exc.__subtype__, **kwargs)
        else:
            return func(instance, exc, **kwargs)
    return wrapped


class RequestMetrics(object):

    def _history(self, active=False):
        if active:
            return self.active_history
        return self.history

    def successful_requests(self, active=False, horizon=None):
        requests = self._history(active=active)
        requests = [request for request in requests if request.confirmed]
        if horizon:
            return requests[int(-1 * horizon):]
        return requests

    def failed_requests(self, active=False, horizon=None):
        requests = self._history(active=active)
        requests = [request for request in requests if request.error]
        if horizon:
            return requests[int(-1 * horizon):]
        return requests

    def timeout_requests(self, active=False, horizon=None):
        requests = self._history(active=active)
        requests = [request for request in requests if request.was_timeout_error]
        if horizon:
            return requests[int(-1 * horizon):]
        return requests

    def requests(self, *args, active=False, horizon=None, **kwargs):

        if kwargs.get('success'):
            return self.successful_requests(active=active, horizon=horizon)

        elif kwargs.get('fail'):
            return self.failed_requests(active=active, horizon=horizon)

        elif kwargs.get('timeout'):
            return self.timeout_requests(active=active, horizon=horizon)

        else:
            requests = self._history(active=active)
            if horizon:
                requests = requests[int(-1 * horizon):]
            if args:
                try:
                    return requests[args[0]]
                except IndexError:
                    return None
            else:
                return requests

    def num_requests(self, **kwargs):
        return len(self.requests(**kwargs))

    def last_request(self, active=False):
        return self.requests(-1, active=active)

    def requests_in_horizon(self, horizon, active=False):
        """
        Returns the number of confirmed requests in the last `horizon` requests.
        If `horizon` not specified, uses the entire history.
        """
        requests = self.requests(active=active, success=True)
        if horizon:
            requests = requests[-horizon:]
        return requests


class ErrorMetrics(object):

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

    def error_rate(self, active=False):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        failed = self.num_requests(active=active, fail=True)
        total = self.num_requests(active=active)

        if total >= self.error_rate_horizon:
            return float(failed) / float(total)
        return 0.0

    @property
    def error_rate_horizon(self):
        """
        The sufficicent number of requests that are required for thte error-rate
        to be a non-zero value.
        """
        err_rate = settings.proxies.pool.limits.get('error_rate', {})
        return err_rate.get('horizon')

    def last_error(self, active=False):
        return self.requests(-1, active=active, fail=True)

    def errors_in_horizon(self, horizon=None, active=False):
        """
        Returns the number of errored requests in the last `horizon` requests.
        """
        confirmed_config = settings.proxies.pool.get('confirmation', {})
        horizon = horizon or confirmed_config.get('horizon')
        if not horizon:
            raise ConfigError("Horizon Not Specified in Config")

        requests = self.requests(active=active, success=False)
        return requests[int(-1 * horizon):]


class ConfirmedMetrics(object):

    def confirmations_in_horizon(self, horizon=None, active=False):
        """
        Returns the number of confirmed requests in the last `horizon` requests.
        """
        confirmed_config = settings.proxies.pool.get('confirmation', {})
        horizon = horizon or confirmed_config.get('horizon')
        if not horizon:
            raise ConfigError("Horizon Not Specified in Config")

        requests = self.requests(active=active, success=True)
        return requests[int(-1 * horizon):]

    def confirmed_in_horizon(self, horizon=None, active=False):
        """
        Returns True if the proxy has a certain number of confirmations in the
        `horizon` most recent requests.
        """
        confirmed_config = settings.proxies.pool.get('confirmation', {})
        horizon = horizon or confirmed_config.get('horizon')
        if not horizon:
            raise ConfigError("Horizon Not Specified in Config")

        requests = self.confirmations_in_horizon(horizon, active=active)
        return len(requests) != 0

    def confirmed_over_threshold(self, threshold=None, active=False, requests=None):
        """
        Returns True if the proxy has a certain number of confirmations in it's
        history.
        """
        confirmed_config = settings.proxies.pool.get('confirmation', {})
        threshold = threshold or confirmed_config.get('threshold')
        if not threshold:
            raise ConfigError("Threshold Not Specified in Config")

        requests = self.num_requests(active=active, success=True)
        return requests >= threshold

    def confirmed_over(self, threshold=None, horizon=None, active=False):
        """
        Based on a `horizon` and `threshold` set in configuration, determines if
        there were either a certain number of confirmations in the most recent
        `horizon` of request history, or if there were a certain number of
        confirmations in all of the request history.
        """
        if not threshold and not horizon:
            raise ValueError("Must specify threshold or horizon.")

        if horizon and not threshold:
            return self.confirmed_in_horizon(horizon, active=active)
        elif threshold and not horizon:
            return self.confirmed_over_threshold(threshold, active=active)
        else:
            requests = self.confirmations_in_horizon(horizon=horizon)
            return len(requests) >= threshold


class TimeoutMetrics(object):

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
    """
    Property accessable and human readable metrics for loggign output
    purposes.
    """
    @property
    def active_times_used(self):
        num_requests = self.num_requests(active=True)
        num_confirmed = self.num_requests(active=True, success=True)
        num_timeouts = self.num_requests(active=True, timeout=True)

        if not num_requests:
            return 'None'
        return (
            f"{num_requests} "
            f"(Confirmed {num_confirmed}/{num_requests}) "
            f"(Time Out Errors {num_timeouts}/{num_requests})"
        )

    @property
    def active_recent_history(self):
        requests = self.requests(active=True, horizon=5)
        readable_history = [
            req.error or "confirmed"
            for req in requests
        ]
        readable_history.reverse()
        return humanize_list(readable_history)

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


class ProxyMetrics(
    RequestMetrics,
    ErrorMetrics,
    ConfirmedMetrics,
    HumanizedMetrics,
    TimeoutMetrics,
):
    def priority(self, count):
        """
        We do not need the confirmed fields since they already are factored
        in based on the separate queues.

        [!] IMPORTANT:
        -------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """
        PROXY_PRIORITY_VALUES = []
        raw_priority_values = settings.proxies.pool.priority

        for priority in raw_priority_values:
            multiplier = int(priority[0])

            metric = priority[1][0]
            params = []
            if len(priority[1]) > 1:
                params = priority[1][1:]
            value = self.get_metric(metric, *params)

            PROXY_PRIORITY_VALUES.append((multiplier, value))

        return tuple([
            field[0] * field[1]
            for field in PROXY_PRIORITY_VALUES
        ] + [count])

    def get_metric(self, metric, *args):
        """
        Arguments can be 1 and up to 3.  The first argument is the metric
        type, the second argument specifies if it is active or historical,
        and the third argument specifies an additional context parameter.

        Certain metrics require a certain number of arguments.

        This is solely so we can define required metrics in configuration and
        more easily and consistently create a method of referencing certain
        metrics.

        [x] TODO
        --------
        Expand on list of metrics and options.
        """
        metrics = ['requests', 'error_rate', 'avg_resp_time']
        if metric not in metrics:
            raise ConfigError("Invalid metric %s." % metric)

        if metric == 'requests':
            active = True if args[0] == 'active' else False
            success = fail = False
            if len(args) > 1:
                success = args[1] == 'success'
                fail = args[1] == 'fail'

            return self.num_requests(active=active, success=success, fail=fail)

        elif metric == 'error_rate':
            active = True if args[0] == 'active' else False
            return self.error_rate(active=active)

        else:
            return self.avg_resp_time
