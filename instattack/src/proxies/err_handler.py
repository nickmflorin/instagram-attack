from instattack import settings
from instattack.src.utils import humanize_list


class ErrorHandlerMixin(object):

    @property
    def error_rate(self):
        if self.num_requests:
            return float(self.num_failed_requests) / self.num_requests
        return 0.0

    @property
    def flattened_error_rate(self):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        if self.num_requests >= settings.ERROR_RATE_HORIZON:
            return float(self.num_failed_requests) / self.num_requests
        return 0.0

    @property
    def humanized_errors(self):
        errors = list(self.errors.keys())
        return humanize_list(errors)

    def _active_error_count(self, *args):
        count = 0
        for err, ct in self.active_errors['all'].items():
            if len(args) != 0 and err in args:
                count += ct
            elif len(args) == 0:
                count += ct
        return count

    @property
    def active_error_count(self):
        return self._active_error_count()

    def _error_count(self, *args):
        count = 0
        for err, ct in self.errors['all'].items():
            if len(args) != 0 and err in args:
                count += ct
            elif len(args) == 0:
                count += ct
        return count

    @property
    def error_count(self):
        return self._error_count()

    def _num_errors(self, error_type=None, active=False):
        error_types = ()
        if error_type:
            error_types = settings.ERROR_TYPE_CLASSIFICATION[error_type]
        if active:
            return self._active_error_count(*error_types)
        return self._error_count(*error_types)

    @property
    def num_connection_errors(self):
        return self._num_errors(error_type='connection')

    @property
    def num_active_connection_errors(self):
        return self._num_errors(error_type='connection', active=True)

    @property
    def num_ssl_errors(self):
        return self._num_errors(error_type='ssl')

    @property
    def num_active_ssl_errors(self):
        return self._num_errors(error_type='ssl', active=True)

    @property
    def num_response_errors(self):
        """
        We do not want to include too_many_requests in here because we still
        want those to be toward front of pool but pulled out based on the
        time since they were used last.
        """
        error_types = list(settings.ERROR_TYPE_CLASSIFICATION['response'])
        error_types.remove('too_many_requests')
        return self._error_count(*error_types)

    @property
    def num_active_response_errors(self):
        """
        We do not want to include too_many_requests in here because we still
        want those to be toward front of pool but pulled out based on the
        time since they were used last.
        """
        error_types = list(settings.ERROR_TYPE_CLASSIFICATION['response'])
        error_types.remove('too_many_requests')
        return self._active_error_count(*error_types)

    def translate_error(self, exc):
        if isinstance(exc, Exception):
            exc = exc.__class__.__name__

        if exc not in settings.ERROR_TRANSLATION:
            raise RuntimeError(f'Unexpected Error {exc}.')
        return settings.ERROR_TRANSLATION[exc]

    def add_error(self, exc, count=1, note_most_recent=True):
        if isinstance(exc, Exception):
            exc = self.translate_error(exc)

        self.errors.setdefault('all', {})
        self.errors['all'].setdefault(exc, 0)
        self.errors['all'][exc] += count

        self.active_errors.setdefault('all', {})
        self.active_errors['all'].setdefault(exc, 0)
        self.active_errors['all'][exc] += count

        if note_most_recent:
            self.errors['most_recent'] = exc
            self.active_errors['most_recent'] = exc

    def include_errors(self, errors):
        for key, val in errors.items():
            self.add_error(key, count=val, note_most_recent=False)

    def get_error_treatment(self, exc):
        if isinstance(exc, Exception):
            exc = exc.__class__.__name__
        return settings.ERROR_TREATMENT_TRANSLATION[exc]

    async def handle_error(self, exc, treatment=None):
        """
        [1] Fatal Error:
        ---------------
        If `remove_invalid_proxy` is set to True and this error occurs,
        the proxy will be removed from the database.
        If `remove_invalid_proxy` is False, the proxy will just be noted
        with the error and the proxy will not be put back in the pool.

        Since we will not delete directly from this method (we need config)
        we will just note the error.

        [2] Inconclusive Error:
        ----------------------
        Proxy will not be noted with the error and the proxy will be put
        back in pool.

        [3] Semi-Fatal Error:
        --------------------
        Regardless of the value of `remove_invalid_proxy`, the  proxy
        will be noted with the error and the proxy will be removed from
        the pool.

        [4] General Error:
        -----------------
        Proxy will be noted with error but put back in the pool.
        """
        if not treatment:
            try:
                treatment = self.get_error_treatment(exc)
            except KeyError:
                raise RuntimeError(f'No treatment classification for error {exc}.')

        self.num_requests += 1

        if treatment == 'fatal':
            self.add_error(exc)

        elif treatment == 'inconclusive':
            return
        else:
            if treatment in ('semifatal', 'error'):
                self.add_error(exc)
            else:
                raise RuntimeError(f'Invalid treatment {treatment}.')
