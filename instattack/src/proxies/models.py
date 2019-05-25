# -*- coding: utf-8 -*-
from datetime import datetime

import tortoise
from tortoise import fields
from tortoise.models import Model

from instattack import logger, settings

from instattack.src.base import ModelMixin
from instattack.src.utils import humanize_list


class ProxyBrokerMixin(object):

    @classmethod
    async def find_for_proxybroker(cls, broker_proxy):
        """
        Finds the related Proxy model for a given proxybroker Proxy model
        and returns the instance if present.
        """
        log = logger.get_async(__name__, subname='find_for_proxybroker')

        try:
            return await cls.get(
                host=broker_proxy.host,
                port=broker_proxy.port,
            )
        except tortoise.exceptions.DoesNotExist:
            return None
        except tortoise.exceptions.MultipleObjectsReturned:
            all_proxies = await cls.filter(host=broker_proxy.host, port=broker_proxy.port).all()
            await log.critical(
                f'Found {len(all_proxies)} Duplicate Proxies for '
                f'{broker_proxy.host} - {broker_proxy.port}.'
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


class Proxy(Model, ModelMixin, ProxyBrokerMixin):

    id = fields.IntField(pk=True)
    host = fields.CharField(max_length=30)
    port = fields.IntField()
    avg_resp_time = fields.FloatField()
    last_used = fields.DatetimeField(null=True)
    date_added = fields.DatetimeField(auto_now_add=True)

    errors = fields.JSONField(default={})
    active_errors = fields.JSONField(default={})

    num_requests = fields.IntField(default=0)
    num_active_requests = fields.IntField(default=0)

    class Meta:
        unique_together = (
            'host',
            'port',
        )

    identifier_fields = (
        'host',
        'port',
    )

    @property
    def unique_id(self):
        """
        Since new proxies will not have an `id`, we can either save those
        proxies when they are created, of we can use another value to indicate
        the uniqueness of the proxy.
        """
        return '-'.join(["%s" % a for a in self.identifier_values])

    @property
    def identifier_values(self):
        return [getattr(self, fld) for fld in self.identifier_fields]

    @property
    def address(self):
        return f'{self.host}:{self.port}'

    @property
    def url(self):
        """
        AioHTTP only supports proxxies with HTTP schemes, so that is the proxy
        type we must fetch from proxybroker and the scheme for the URL we must
        use with our requests.
        """
        scheme = 'http'
        return f"{scheme}://{self.address}/"

    @property
    def num_successful_requests(self):
        return self.num_requests - self.error_count

    @property
    def num_active_successful_requests(self):
        return self.num_active_requests - self.active_error_count

    @property
    def num_failed_requests(self):
        return self.num_requests - self.num_successful_requests

    @property
    def num_active_failed_requests(self):
        return self.num_active_requests - self.num_active_successful_requests

    @property
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return 0.0

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
    def active_error_count(self):
        count = 0
        for err, ct in self.active_errors.items():
            count += ct
        return count

    def _error_count(self, *args):
        count = 0
        for err, ct in self.errors.items():
            if len(args) != 0 and err in args:
                count += ct
            elif len(args) == 0:
                count += ct
        return count

    @property
    def error_count(self):
        return self._error_count()

    @property
    def humanized_errors(self):
        errors = list(self.errors.keys())
        return humanize_list(errors)

    @property
    def num_connection_errors(self):
        return self._error_count(*settings.CONNECTION_ERRORS)

    def translate_error(self, exc):
        if isinstance(exc, Exception):
            exc = exc.__class__.__name__

        if exc not in settings.ERROR_TRANSLATION:
            raise RuntimeError(f'Unexpected Error {exc}.')
        return settings.ERROR_TRANSLATION[exc]

    def add_error(self, exc):
        if isinstance(exc, Exception):
            exc = self.translate_error(exc)

        self.errors.setdefault(exc, 0)
        self.errors[exc] += 1

        self.active_errors.setdefault(exc, 0)
        self.active_errors[exc] += 1

    def include_errors(self, errors):
        for key, val in errors.items():

            self.errors.setdefault(key, 0)
            self.errors[key] += val

            self.active_errors.setdefault(key, 0)
            self.active_errors[key] += 1

    def reset(self):
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        self.num_active_requests = 0
        self.active_errors = {}

    def priority(self, count):
        from .score import priority
        return priority(self, count)

    def update_time(self):
        self.last_used = datetime.now()

    async def was_success(self, save=True):
        self.num_requests += 1
        if save:
            await self.save()

    async def was_error(self, exc, save=True):
        self.add_error(exc)
        self.num_requests += 1
        if save:
            await self.save()

    async def was_inconclusive(self, save=True):
        self.num_requests += 1
        if save:
            await self.save()

    async def save(self, *args, **kwargs):
        """
        We don't want to reset num_active_requests and active_errors here
        because we save the proxy intermittedly throughout the operation.
        """
        log = logger.get_async(__name__, subname='save')

        if not self.errors:
            self.errors = {}

        for key, val in self.errors.items():
            if key not in settings.ERROR_TRANSLATION.values():
                if key not in settings.ERROR_TRANSLATION.keys():
                    log.error(f'Invalid Error Name: {key}... Removing Error')
                else:
                    translated = settings.ERROR_TRANSLATION[key]
                    log.error(f'Unrecognized Error Name: {key}... Translating to {translated}.')

                    self.errors[translated] = self.errors[key]
                    del self.errors[key]

        await super(Proxy, self).save(*args, **kwargs)
