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
from instattack.conf import settings
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
        raise Exception('If duplicates found, use oldest proxy and delete others...')
        try:
            return await cls.get(
                host=proxy.host,
                port=proxy.port,
            )
        except tortoise.exceptions.DoesNotExist:
            return None
        except tortoise.exceptions.MultipleObjectsReturned:

            log.critical(f'Found Multiple Proxies for {proxy.host} - {proxy.port}.')
            use_proxy = cls.filter(host=proxy.host, port=proxy.port).all()[0]

    @classmethod
    async def from_proxybroker(cls, broker_proxy):
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
            # Only do this for as long as we are not measuring this value ourselves.
            proxy.avg_resp_time = broker_proxy.avg_resp_time
            return proxy
        else:
            proxy = Proxy(
                host=broker_proxy.host,
                port=broker_proxy.port,
                avg_resp_time=broker_proxy.avg_resp_time,
            )
            return proxy

    @classmethod
    async def create_from_proxybroker(cls, broker_proxy):
        proxy = await cls.from_proxybroker(broker_proxy)
        await proxy.save()
        return proxy


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
        if self.num_requests >= 5:
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
    invalid = fields.BooleanField(default=False)

    # Confirmed means that the last request this was used for did not result in
    # an error that would cause it to be invalid, but instead resulted in a
    # a result or in an error that does not rule out the validity of the proxy.
    confirmed = fields.BooleanField(default=False)

    errors = fields.JSONField(default={})
    num_successful_requests = fields.IntField(default=0)
    num_failed_requests = fields.IntField(default=0)
    num_active_requests = fields.IntField(default=0)

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

    def compare(self, other, return_difference=False):
        if any([
            other.identifier_values[i] != self.identifier_values[i]
            for i in range(len(self.identifier_fields))
        ]):
            raise RuntimeError('Cannot compare these two proxies.')

        if self.priority != other.priority:
            if return_difference:
                return ProxyDifferences(old_proxy=self, new_proxy=other)
            return True
        else:
            if return_difference:
                return None
            return False

    def evaluate(self, num_requests=None, error_rate=None, resp_time=None):
        """
        Determines if the proxy meets the provided standards.
        """

        # We might want to lower restrictions on num requests, since we can
        # just put in the back of the pool.
        if num_requests and self.num_requests >= num_requests:
            return (False, 'Number of Requests Exceeds Limit')

        elif error_rate and self.error_rate > error_rate:
            return (False, 'Error Rate too Large')

        elif resp_time and self.avg_resp_time > resp_time:
            return (False, 'Avg. Response Time too Large')

        return (True, None)

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
            log.debug('Saving Proxy with Error: %s' % err_name)
            await self.save()

    async def was_inconclusive(self, save=True):
        self.update_time()
        if save:
            await self.save()

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
        if self.confirmed and self.invalid:
            raise tortoise.exceptions.IntegrityError(
                f"Proxy cannot be both confirmed and invalid.")

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
