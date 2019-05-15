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

from instattack import settings
from instattack.lib import validate_method

from instattack.core.mixins import ModelMixin


__all__ = ('Proxy', )


class ProxyBrokerMixin(object):

    @classmethod
    async def find_for_proxybroker(cls, proxy, method):
        """
        Finds the related Proxy model for a given proxybroker Proxy model
        and returns the instance if present.
        """
        try:
            return await cls.get(
                host=proxy.host,
                port=proxy.port,
                method=method,
                schemes=list(proxy.schemes)
            )
        except tortoise.exceptions.DoesNotExist:
            return None

    @classmethod
    async def from_proxybroker(cls, broker_proxy, method):
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

        proxy = await cls.find_for_proxybroker(broker_proxy, method)
        if proxy:
            # Only do this for as long as we are not measuring this value ourselves.
            proxy.avg_resp_time = broker_proxy.avg_resp_time
            return proxy
        else:
            proxy = Proxy(
                host=broker_proxy.host,
                port=broker_proxy.port,
                method=method,
                avg_resp_time=broker_proxy.avg_resp_time,
                error_rate=broker_proxy.error_rate,
                schemes=list(broker_proxy.schemes),
            )
            return proxy

    @classmethod
    async def create_from_proxybroker(cls, broker_proxy, method):
        proxy = await cls.from_proxybroker(broker_proxy, method)
        await proxy.save()
        return proxy


class Proxy(Model, ModelMixin, ProxyBrokerMixin):

    id = fields.IntField(pk=True)
    host = fields.CharField(max_length=30)
    port = fields.IntField()
    avg_resp_time = fields.FloatField()
    last_used = fields.DatetimeField(null=True)
    method = fields.CharField(max_length=4)
    schemes = fields.JSONField(default=[])

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
        'method'
    )

    class Meta:
        unique_together = (
            'host',
            'port',
            'method'
        )

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

    def reset(self):
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        self.num_active_requests = 0

    @property
    def priority_values(self):
        return [field[0] * getattr(self, field[1]) for field in self.priority_fields]

    def priority(self, count):
        priority = self.priority_values[:]
        priority.append(count)
        return tuple(priority)

    def add_error(self, exc):
        """
        TODO: Come up with a better error classification scheme.
        """
        err_name = exc.__class__.__name__
        if err_name in self.errors:
            self.errors[err_name] += 1
        else:
            self.errors[err_name] = 1

    def success(self):
        self.update_time()
        self.num_successful_requests += 1
        self.invalid = False
        self.confirmed = True

    def inconclusive(self):
        self.update_time()

    def error(self, e):
        self.update_time()
        self.add_error(e)
        self.num_failed_requests += 1
        self.invalid = True
        self.confirmed = False

    def update_time(self):
        self.last_used = datetime.now()

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

        # AioHTTP only supports proxxies with HTTP schemes
        elif 'HTTP' not in self.schemes:
            return (False, f'Scheme {scheme} Not Supported')

        return (True, None)

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

    async def save(self, *args, **kwargs):
        if self.method not in ["GET", "POST"]:
            raise tortoise.exceptions.IntegrityError(f"Invalid method {self.method}.")

        if self.confirmed and self.invalid:
            raise tortoise.exceptions.IntegrityError(
                f"Proxy cannot be both confirmed and invalid.")

        if not self.errors:
            self.errors = {}

        if not self.schemes:
            raise tortoise.exceptions.IntegrityError('Schemes required.')
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
