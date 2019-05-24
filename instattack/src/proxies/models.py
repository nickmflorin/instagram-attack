# -*- coding: utf-8 -*-
import asyncio
from collections import Counter
import json

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

import tortoise
from tortoise import fields
from tortoise.models import Model

from instattack import logger
from instattack import settings
from instattack.src.base import ModelMixin


__all__ = ('Proxy', )


log = logger.get_async('Proxy Model')


class ProxyBrokerMixin(object):

    @classmethod
    async def find_for_proxybroker(cls, proxy):
        """
        Finds the related Proxy model for a given proxybroker Proxy model
        and returns the instance if present.
        """
        try:
            return await cls.get(
                host=proxy.host,
                port=proxy.port,
            )
        except tortoise.exceptions.DoesNotExist:
            return None
        except tortoise.exceptions.MultipleObjectsReturned:
            all_proxies = await cls.filter(host=proxyx.host, port=proxy.port).all()
            all_proxies = sorted(all_proxies, key=lambda x: x.date_added)
            log.critical(
                f'Found {len(all_proxies)} Duplicate Proxies for {proxy.host} - {proxy.port}.')

            for proxy in all_proxies[1:]:
                log.warning('Deleting Duplicate Proxy', extra={'proxy': proxy})
                await proxy.delete()

            return all_proxies[0]

    @classmethod
    def translate_proxybroker_errors(cls, broker_proxy):
        log = logger.get_sync(__name__, subname='translate_proxybroker_errors')

        errors = {}
        for err, count in broker_proxy.stat['errors'].__dict__.items():
            if err in settings.PROXY_BROKER_ERROR_TRANSLATION:
                errors[translation[err]] = count
            else:
                log.warning(f'Unexpected Proxy Broker Error: {err}.')
                errors[err] = count
        return errors

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

        # Figure out how to translate this to our system.
        broker_errors = broker_proxy.stat['errors']

        proxy = await cls.find_for_proxybroker(broker_proxy)
        if proxy:
            errors = cls.translate_proxybroker_errors(broker_proxy)
            proxy.include_errors(errors)
            proxy.num_requests += broker_proxy.stat['requests']

            # Only do this for as long as we are not measuring this value ourselves.
            # When we start measuring ourselves, we are not going to want to
            # overwrite it.
            proxy.avg_resp_time = broker_proxy.avg_resp_time
            if save:
                await proxy.save()
            return proxy, False
        else:
            proxy = Proxy(
                host=broker_proxy.host,
                port=broker_proxy.port,
                avg_resp_time=broker_proxy.avg_resp_time,
                errors=cls.translate_proxybroker_errors(broker_proxy),
                num_requests=broker_proxy.stat['requests'],
            )
            if save:
                await proxy.save()
            return proxy, True


class ProxyModelMixin(ModelMixin):

    @property
    def priority_values(self):
        return [field[0] * getattr(self, field[1]) for field in self.priority_fields]

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
    def num_requests(self):
        return self.num_successful_requests + self.num_failed_requests

    @property
    def state(self):
        if self.confirmed:
            return 1
        elif self.invalid:
            return -1
        return 0

    @property
    def humanized_state(self):
        if self.confirmed:
            return 'Confirmed'
        elif self.invalid:
            return 'Invalid'
        return 'Inconclusive'

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
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return 0.0

    @property
    def identifier_values(self):
        return [getattr(self, field) for field in self.identifier_fields]

    @property
    def unique_id(self):
        """
        Since new proxies will not have an `id`, we can either save those
        proxies when they are created, of we can use another value to indicate
        the uniqueness of the proxy.
        """
        return '-'.join(["%s" % a for a in self.identifier_values])


class Proxy(Model, ProxyModelMixin, ProxyBrokerMixin):

    id = fields.IntField(pk=True)
    host = fields.CharField(max_length=30)
    port = fields.IntField()
    avg_resp_time = fields.FloatField()
    last_used = fields.DatetimeField(null=True)
    date_added = fields.DatetimeField(auto_now_add=True)

    # Invalid means that the last request this was used for resulted in a
    # fatal error.
    # invalid = fields.BooleanField(default=False)

    # Confirmed means that the last request this was used for did not result in
    # an error that would cause it to be invalid, but instead resulted in a
    # a result or in an error that does not rule out the validity of the proxy.
    # confirmed = fields.BooleanField(default=False)

    errors = fields.JSONField(default={})
    num_requests = fields.IntField(default=0)

    # Used to determine if the proxy is fundamentally different in database.
    priority_fields = (
        (-1, 'state'),
        (-1, 'num_successful_requests'),
        (1, 'flattened_error_rate'),
        (-1, 'time_since_used'),
        (1, 'avg_resp_time'),
    )

    identifier_fields = (
        'host',
        'port',
    )

    class Meta:
        unique_together = (
            'host',
            'port',
        )

    def reset(self):
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        self.num_active_requests = 0

    def priority(self, count):
        priority = self.priority_values[:]
        priority.append(count)
        return tuple(priority)

    def update_time(self):
        self.last_used = datetime.now()

    async def was_success(self, save=True):

        self.update_time()
        self.num_successful_requests += 1
        self.invalid = False
        self.confirmed = True

        if save:
            await self.save()

    async def was_error(self, exc, save=True):
        """
        TODO: Come up with a better error classification scheme.
        """
        err_name = exc.__class__.__name__
        self.errors.setdefault(err_name, 0)
        self.errors[err_name] += 1

        self.update_time()
        self.invalid = True
        self.confirmed = False
        self.num_failed_requests += 1
        if save:
            await self.save()

    async def was_inconclusive(self, save=True):
        self.update_time()
        if save:
            await self.save()

    def __eq__(self, other):
        if all([
            other.identifier_values[i] == self.identifier_values[i]
            for i in range(len(self.identifier_fields))
        ]):
            return True
        return False

    def include_errors(self, errors):
        for key, val in errors.items():
            if key in self.errors:
                self.errors[key] += val
            else:
                self.errors[key] = val

    def different_from(self, other):
        if any([
            other.priority_values[i] != self.priority_values[i]
                for i in range(len(self.priority_fields))
        ]):
            return True
        return False

    def compare(self, other, return_difference=False):
        if self == other:
            raise RuntimeError('Proxies must be different in order to compare.')

        if self.different_from(other):
            if return_difference:
                return ProxyDifferences(old_proxy=self, new_proxy=other)
            return True
        else:
            if return_difference:
                return None
            return False

    def evaluate(self, max_error_rate=None, min_req_proxy=None, max_resp_time=None):
        """
        Determines if the proxy meets the provided standards.
        """
        evaluations = []
        if (min_req_proxy and min_req_proxy.get('value') and
                self.num_active_requests >= min_req_proxy['value']):

            num_requests = min_req_proxy['value']
            evaluations.append({
                'strict': min_req_proxy['strict'],
                'attr': 'min_req_proxy',
                'reason': f'Num. Active Requests {self.num_active_requests} > {num_requests}'
            })

        if (max_error_rate and max_error_rate.get('value') and
                self.flattened_error_rate >= max_error_rate['value']):

            err_rate = max_error_rate['value']
            evaluations.append({
                'strict': max_error_rate['strict'],
                'attr': 'max_error_rate',
                'reason': f'Error Rate {self.error_rate} > {err_rate}.'
            })

        if (max_resp_time and max_resp_time.get('value') and
                self.avg_resp_time >= max_resp_time['value']):

            resp_time = max_resp_time['value']
            evaluations.append({
                'strict': max_resp_time['strict'],
                'attr': 'max_resp_time',
                'reason': f'Avg. Resp. Time {self.avg_resp_time} > {resp_time}.'
            })

        return evaluations

    async def update_from_differences(self, differences):
        for diff in differences.diff:
            try:
                setattr(self, diff.attr, diff.new_value)
            except AttributeError:
                # Right now, this might include properties on the model too,
                # since we use the differences object for other things.
                pass
        await self.save()

    async def save(self, *args, **kwargs):
        if not self.errors:
            self.errors = {}
        await super(Proxy, self).save(*args, **kwargs)


@dataclass
class ProxyDifference:

    attr: str
    old_value: Any = None
    new_value: Any = None

    def __post_init__(self):
        if not self.new_value and not self.old_value:
            raise ValueError("Must provide either new_value or old_value.")
        elif self.new_value == self.old_value:
            raise ValueError("There was no change.")

    def __str__(self):
        if self.old_value and self.new_value:
            return f"{self.attr}: {self.old_value} -> {self.new_value}"
        elif self.new_value and not self.old_value:
            return f"{self.attr}: + {self.new_value}"
        else:
            return f"{self.attr}: - {self.old_value}"


@dataclass
class ProxyDifferences:
    old_proxy: Proxy
    new_proxy: Proxy
    diff: List[ProxyDifference] = field(init=False)

    def __post_init__(self):
        self.diff = []
        for i in range(len(self.old_proxy.priority_fields)):
            old_value = self.old_proxy.priority_values[i]
            new_value = self.new_proxy.priority_values[i]
            if old_value != new_value:
                self.add(
                    self.old_proxy.priority_fields[i][1],
                    old_value,
                    new_value
                )

    def add(self, attr, old, new):
        diff = ProxyDifference(attr=attr, old_value=old, new_value=new)
        self.diff.append(diff)

    @property
    def none(self):
        return len(self.diff) == 0

    def __str__(self):
        strings = [str(d) for d in self.diff]
        return ', '.join(strings)
