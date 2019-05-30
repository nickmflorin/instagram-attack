# -*- coding: utf-8 -*-
import tortoise

from instattack.app import settings
from instattack.conf import Configuration

from instattack.lib import logger
from instattack.lib.utils import humanize_list


log = logger.get_async(__name__)


class ProxyBrokerMixin(object):

    @classmethod
    async def find_for_proxybroker(cls, broker_proxy):
        """
        Finds the related Proxy model for a given proxybroker Proxy model
        and returns the instance if present.
        """
        try:
            return await cls.get(
                host=broker_proxy.host,
                port=broker_proxy.port,
            )
        except tortoise.exceptions.DoesNotExist:
            return None
        except tortoise.exceptions.MultipleObjectsReturned:
            all_proxies = await cls.filter(host=broker_proxy.host, port=broker_proxy.port).all()
            await log.warning(
                f'Found {len(all_proxies)} Duplicate Proxies for '
                f'{broker_proxy.host} - {broker_proxy.port}.',
                extra={
                    'other': f'Deleting {len(all_proxies) - 1} Duplicates...'
                }
            )

            all_proxies = sorted(all_proxies, key=lambda x: x.date_added)
            for proxy in all_proxies[1:]:
                await log.warning('Deleting Duplicate Proxy', extra={'proxy': proxy})
                await proxy.delete()

            return all_proxies[0]

    @classmethod
    def translate_proxybroker_errors(cls, broker_proxy):
        log = logger.get_sync(__name__, subname='translate_proxybroker_errors')

        errors = {}
        for err, count in broker_proxy.stat['errors'].__dict__.items():
            if err in settings.PROXY_BROKER_ERROR_TRANSLATION:
                errors[settings.PROXY_BROKER_ERROR_TRANSLATION[err]] = count
            else:
                log.warning(f'Unexpected Proxy Broker Error: {err}.')
                errors[err] = count
        return errors

    async def update_from_proxybroker(self, broker_proxy, save=False):
        errors = self.translate_proxybroker_errors(broker_proxy)

        self.include_errors(errors)
        self.num_requests += broker_proxy.stat['requests']

        # Only do this for as long as we are not measuring this value ourselves.
        # When we start measuring ourselves, we are not going to want to
        # overwrite it.
        self.avg_resp_time = broker_proxy.avg_resp_time
        if save:
            await self.save()

    @classmethod
    async def create_from_proxybroker(cls, broker_proxy, save=False):
        from .models import Proxy

        proxy = Proxy(
            host=broker_proxy.host,
            port=broker_proxy.port,
            avg_resp_time=broker_proxy.avg_resp_time,
            errors=cls.translate_proxybroker_errors(broker_proxy),
            num_requests=broker_proxy.stat['requests'],
        )
        if save:
            await proxy.save()
        return proxy

    @classmethod
    async def update_or_create_from_proxybroker(cls, broker_proxy, save=False):
        """
        Finds the possibly related Proxy instance for a proxybroker Proxy instance
        and updates it with relevant info from the proxybroker instance if
        present, otherwise it will create a new Proxy instance using the information
        from the proxybroker instance.

        TODO
        ----
        Figure out a way to translate proxybroker errors to our error system so
        they can be reconciled.
        """
        proxy = await cls.find_for_proxybroker(broker_proxy)
        if proxy:
            await proxy.update_from_proxybroker(broker_proxy, save=save)
            return proxy, False
        else:
            proxy = await cls.create_from_proxybroker(broker_proxy, save=save)
            return proxy, True


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

        [x] TODO:
        --------
        Figure out how to not require the configuration to be reloaded for these
        property parameters.
        """

        # We are not storing configuration as an environment variable anymore, so
        # we have to investigate another way to do this.  For now, we will just use
        # a constant.
        # config = Configuration.load()
        # error_rate_horizon = config['proxies']['pool']['error_rate_horizon']

        error_rate_horizon = 5
        if self.num_requests >= error_rate_horizon:
            return float(self.num_failed_requests) / self.num_requests
        return 0.0

    @property
    def humanized_errors(self):
        all_errors = self.errors.get('all', {})
        errors = list(all_errors.keys()) or None
        return humanize_list(errors)

    @property
    def humanized_error_count(self):
        return f"{self.error_count} (Active: {self.active_error_count})"

    @property
    def humanized_connection_error_count(self):
        return f"{self.num_connection_errors} (Active: {self.num_active_connection_errors})"

    @property
    def humanized_response_error_count(self):
        return f"{self.num_response_errors} (Active: {self.num_active_response_errors})"

    @property
    def humanized_ssl_error_count(self):
        return f"{self.num_ssl_errors} (Active: {self.num_active_ssl_errors})"

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
        all_errors = self.errors.get('all', {})
        for err, ct in all_errors.items():
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
    def num_timeout_errors(self):
        return self._num_errors(error_type='timeout')

    @property
    def num_ssl_errors(self):
        return self._num_errors(error_type='ssl')

    @property
    def num_response_errors(self):
        return self._num_errors(error_type='invalid_response')

    @property
    def num_active_response_errors(self):
        return self._num_errors(error_type='invalid_response', active=True)

    @property
    def num_instagram_errors(self):
        return self._num_errors(error_type='instagram')

    @property
    def num_active_connection_errors(self):
        return self._num_errors(error_type='connection', active=True)

    @property
    def num_active_timeout_errors(self):
        return self._num_errors(error_type='timeout', active=True)

    @property
    def num_too_many_requests_errors(self):
        return self._num_errors(error_type='too_many_requests')

    @property
    def num_active_ssl_errors(self):
        return self._num_errors(error_type='ssl', active=True)

    @property
    def num_active_instagram_errors(self):
        return self._num_errors(error_type='instagram', active=True)

    @property
    def num_active_too_many_requests_errors(self):
        return self._num_errors(error_type='too_many_requests', active=True)

    def add_error(self, exc, count=1, note_most_recent=True):

        self.errors.setdefault('all', {})
        self.errors['all'].setdefault(exc.__subtype__, 0)
        self.errors['all'][exc.__subtype__] += count

        self.active_errors.setdefault('all', {})
        self.active_errors['all'].setdefault(exc.__subtype__, 0)
        self.active_errors['all'][exc.__subtype__] += count

        if note_most_recent:
            self.errors['most_recent'] = exc.__subtype__
            self.active_errors['most_recent'] = exc.__subtype__

    def include_errors(self, errors):
        for key, val in errors.items():
            self.add_error(key, count=val, note_most_recent=False)

    async def handle_success(self, save=False):
        self.num_requests += 1
        if save:
            await self.save()

    async def handle_error(self, exc):
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
        self.num_requests += 1
        self.add_error(exc)
