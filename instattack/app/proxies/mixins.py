# -*- coding: utf-8 -*-
from datetime import datetime

from instattack import settings
from instattack.lib.utils import humanize_list

from .evaluation import evaluate_for_pool, evaluate_from_pool


class HumanizedMetrics(object):

    @property
    def humanized_errors(self):
        all_errors = self.errors.get('all', {})
        errors = list(all_errors.keys()) or []
        return humanize_list(errors)

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


class EvaluationMixin(HumanizedMetrics):

    def hold(self, config):
        """
        If the Proxy just resulted in a num_requests error, we don't want to
        put back in the Pool immediately because it will have a high priority
        and will likely slow down the retrieval of subsequent proxies because
        it cannot be used just yet.

        Instead, we put in an array to hold onto until it is ready to be used.
        """
        config = config['proxies']['pool']['limits']

        if (self.active_errors.get('most_recent') and
                self.active_errors['most_recent'] == 'too_many_requests'):
            if self.time_since_used < config['too_many_requests_delay']:
                return True
        return False

    def _num_requests(self, active=False, success=None):
        if success is False:
            return self._num_errors(active=active)
        else:
            value = self.num_requests
            if active:
                value = self.num_active_requests
            if success is True:
                return value - self._num_errors(active=active)
            return value

    def _error_rate(self, active=False, horizon=5):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.

        [x] TODO:
        --------
        Figure out how to not require the configuration to be reloaded for these
        property parameters.
        """
        if self._num_requests(active=active) >= horizon:
            return (float(self._num_requests(active=active, success=False)) /
                self._num_requests(active=active))
        return 0.0

    def _num_errors(self, *args, active=False):
        errors = self.errors if not active else self.active_errors
        all_errors = errors.get('all', {})

        search_errors = list(args)

        # Allows More Specific Error Types to be Passed In
        generalized = []
        for err in search_errors:
            if err in settings.ERROR_TYPE_CLASSIFICATION:
                generalized.append(settings.ERROR_TYPE_CLASSIFICATION[err])
            else:
                generalized.append(err)

        count = 0
        for err, ct in all_errors.items():
            if not search_errors:
                count += ct
            else:
                if err in search_errors:
                    count += ct
        return count

    @property
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return 0.0

    def evaluate_for_pool(self, config):
        """
        Called before a proxy is put into the Pool.

        Allows us to disregard or completely ignore proxies without having
        to delete them from DB.

        [x] TODO:
        --------
        Incorporate limit on certain errors or exclusion of proxy based on certain
        errors in general.

        Make it so that we can return the evaluations and also indicate
        that it is okay or not okay for the pool.
        """
        evaluation = evaluate_for_pool(self, config)
        return evaluation

    def evaluate_for_use(self, config):
        """
        Called before a proxy is returned from the Pool.  This is where we want to
        evaluate things that would not prevent a proxy from going into the pool,
        but just from being pulled out at that moment.

        This should incorporate timing aspects and things of that nature.
        Can include more custom logic indicating the desired use of the
        proxy than we can do with the priority alone.
        """
        evaluation = evaluate_from_pool(self, config)
        return evaluation
