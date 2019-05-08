# -*- coding: utf-8 -*-
from __future__ import absolute_import

from collections import Counter
import json

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

from tortoise.models import Model
from tortoise import fields

from lib import validate_method
from instattack import settings


__all__ = ('Proxy', 'ProxyError', )


class ModelMixin(object):

    @classmethod
    def count(cls):
        """
        Do not ask me why the count() method returns a CountQuery that does
        not have an easily accessible integer value.
        """
        return cls.all().count().__sizeof__()


class ProxyError(Model, ModelMixin):
    # TODO: Add message field.
    id = fields.IntField(pk=True)
    proxy = fields.ForeignKeyField('models.Proxy', related_name='errors')
    name = fields.CharField(max_length=30)
    num = fields.IntField(default=0)

    class Meta:
        unique_together = ('name', 'proxy')


class Proxy(Model, ModelMixin):
    """
    TODO:
    ----

    Start storing successful requests vs. unsuccessful requests.
    """

    # Used to determine if the proxy is fundamentally different in database.
    comparison_fields = ('avg_resp_time', 'error_rate', )

    def get_default_scheme(context):
        method = context.get_current_parameters()['method']
        return [settings.DEFAULT_SCHEMES[method]]

    id = fields.IntField(pk=True)
    host = fields.CharField(max_length=30)
    port = fields.IntField()
    avg_resp_time = fields.FloatField()
    error_rate = fields.FloatField()
    last_used = fields.DatetimeField(null=True)
    num_requests = fields.IntField(default=0)
    method = fields.CharField(max_length=4)
    schemes = fields.JSONField()

    class Meta:
        unique_together = ('host', 'port', 'method')

    @property
    def unique_id(self):
        """
        Since new proxies will not have an `id`, we can either save those
        proxies when they are created, of we can use another value to indicate
        the uniqueness of the proxy.
        """
        return f"{self.host}-{self.port}-{self.method}"

    @property
    def comparison_data(self):
        return dict([(key, val) for key, val in
            zip(self.comparison_fields,
                [getattr(self, field) for field in self.comparison_fields])])

    def compare(self, other, return_difference=False):
        if self.comparison_data != other.comparison_data:
            if return_difference:
                return ProxyDifferences(old_proxy=self, new_proxy=other)
            return True
        else:
            if return_difference:
                return None
            return False

    async def save(self, *args, **kwargs):
        if self.method not in ["GET", "POST"]:
            raise tortoise.exceptions.IntegrityError(f"Invalid method {self.method}.")

        if not self.schemes:
            self.schemes = [settings.DEFAULT_SCHEMES[self.method]]
        await super(Proxy, self).save(*args, **kwargs)

    @classmethod
    async def from_proxybroker(cls, proxy, method, save=False):
        """
        We need to reimplement the handling of errors from the proxy broker
        so they can possibly translate more easiy.
        """
        # TODO: Maybe find a way to translate proxy broker errors to our error
        # system.
        broker_errors = proxy.stat['errors']

        model_errors = []
        _proxy = Proxy(
            host=proxy.host,
            port=proxy.port,
            method=method,
            avg_resp_time=proxy.avg_resp_time,
            error_rate=proxy.error_rate,
            num_requests=0,  # Our reference of num_requests differs from ProxyBroker
            schemes=list(proxy.schemes),
        )
        if save:
            await _proxy.save()
        return _proxy

    async def find_error(self, exc):
        errors = await self.fetch_related('errors')
        if not errors:
            return None

        err_name = exc.__class__.__name__
        if err_name in [err.name for err in errors.all()]:
            ind = [i for i in range(len(errors)) if errors[i].name == err_name]
            return errors[ind]
        return None

    async def add_error(self, exc):
        err_name = exc.__class__.__name__

        err = await self.find_error(exc)
        if not err:
            err = ProxyError(proxy=self, name=err_name, num=1)
        else:
            err.num = err.num + 1

        # Make sure we want to save the errors now.
        await err.save()
        self.update_requests()

    def update_requests(self):
        self.update_time()
        self.num_requests += 1

    def update_time(self):
        self.last_used = datetime.now()

    def evaluate(self, num_requests=None, error_rate=None, resp_time=None, scheme=None):
        """
        Determines if the proxy meets the provided standards.
        """
        if self.num_requests >= num_requests:
            return (False, 'Number of Requests Exceeds Limit')

        elif self.error_rate > error_rate:
            return (False, 'Error Rate too Large')

        elif self.avg_resp_time > resp_time:
            return (False, 'Avg. Response Time too Large')

        elif scheme not in self.schemes:
            return (False, f'Scheme {scheme} Not Supported')

        return (True, None)

    @property
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return None

    @property
    def priority(self):
        # This is from ProxyBroker model
        # We are going to want to update this for our use case.
        return (self.error_rate, self.avg_resp_time)

    @property
    def address(self):
        return f'{self.host}:{self.port}'

    def url(self, scheme='http'):
        return f"{scheme}://{self.address}/"


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
        for key in self.old_proxy.comparison_fields:
            if getattr(self.old_proxy, key) != getattr(self.new_proxy, key):
                self.add(key, getattr(self.old_proxy, key), getattr(self.new_proxy, key))

    def add(self, attr, old, new):
        diff = ProxyDifference(attr=attr, old_value=old, new_value=new)
        self.diff.append(diff)

    @property
    def none(self):
        return len(self.diff) == 0

    def __str__(self):
        strings = [str(d) for d in self.diff]
        return ', '.join(strings)