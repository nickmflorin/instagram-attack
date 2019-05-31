# -*- coding: utf-8 -*-
from datetime import datetime

import tortoise
from tortoise import fields
from tortoise.models import Model

from instattack.config import settings
from instattack.lib import logger

from .mixins import EvaluationMixin


class Proxy(Model, EvaluationMixin):

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
    last_request_confirmed = fields.BooleanField(default=False)
    last_error = fields.CharField(max_length=15, null=True)

    class Meta:
        unique_together = ('host', 'port')

    identifier_fields = ('host', 'port')

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

    def reset(self):
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        self.num_active_requests = 0
        self.active_errors = {}
        self.last_active_error = None

    def update_time(self):
        self.last_used = datetime.now()

    def priority_values(self, config):
        err_rate = config['instattack']['proxies']['limits'].get('error_rate', {})
        horizon = err_rate.get('horizon')

        PROXY_PRIORITY_VALUES = (
            (-1, self.last_request_confirmed),
            (-1, self._num_requests(active=False, success=True)),
            (1, self._error_rate(active=False, horizon=horizon)),
            (1, self.avg_resp_time),
        )

        return [
            field[0] * field[1]
            for field in PROXY_PRIORITY_VALUES
        ]

    def priority(self, count, config):
        priority = self.priority_values(config)
        priority.append(count)
        return tuple(priority)

    def set_recent_error(self, exc, historical=True, active=False):
        error_attr = {
            (True, False): ('last_error',),
            (False, True): ('last_active_error',),
            (True, True): ('last_error', 'last_active_error',),
        }
        attrs = error_attr[(historical, active)]
        for attr in attrs:
            setattr(self, attr, exc.__subtype__)

    def add_error(self, exc, count=1, historical=True, active=False, recent=False):
        error_attr = {
            (True, False): ('errors',),
            (False, True): ('active_errors',),
            (True, True): ('errors', 'active_errors',),
        }
        attrs = error_attr[(historical, active)]
        for attr in attrs:
            errors = getattr(self, attr)
            errors.setdefault(exc.__subtype__, 0)
            errors[exc.__subtype__] += count

        if recent:
            self.set_recent_error(exc, historical=historical, active=active)

    def include_errors(self, errors):
        for key, val in errors.items():
            self.add_error(
                key,
                count=val,
                active=True,
                historical=True,
            )

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

    async def save(self, reset=True, *args, **kwargs):
        """
        We don't want to reset num_active_requests and active_errors here
        because we save the proxy intermittedly throughout the operation.
        """
        if reset:
            self.reset()
        await super(Proxy, self).save(*args, **kwargs)
