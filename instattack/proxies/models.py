# -*- coding: utf-8 -*-
from __future__ import absolute_import

from collections import Counter

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

from instattack import validate_method


@dataclass
class RequestProxy:

    host: str
    port: int
    method: str
    avg_resp_time: float
    error_rate: float
    errors: field(default_factory=Counter)  # Not Currently Used
    saved: bool = False
    last_used: datetime = None
    num_requests: int = 0  # Not Currently Used
    schemes: tuple = ()

    @property
    def id(self):
        """
        Uniquely defines the proxy for purposes of maintaining the same proxies
        in the heapq.
        """
        return f'{self.host}-{self.port}-{self.method}'

    @property
    def comparison_data(self):
        data = self.__dict__.copy()
        del data['saved']
        return data

    def __eq__(self, other):
        """
        For purposes of comparing proxies, we care about all values except the
        `saved` value, which just tells us if it was retrieved from a text file
        or from the broker.
        """
        if other.__class__ is not self.__class__:
            return NotImplemented
        return self.comparison_data == other.comparison_data
        #return (self.host, self.port, self.method) == (other.host, other.port, other.method)

    def __diff__(self, new_proxy):
        differences = ProxyDifferences(old_proxy=self, new_proxy=new_proxy)

        current = self.comparison_data
        new = new_proxy.comparison_data
        for key, val in current.items():
            if val != new[key]:
                differences.add(key, val, new[key])
        return differences

    def __post_init__(self):
        validate_method(self.method)

    @classmethod
    def from_proxybroker(cls, proxy, method):
        return RequestProxy(
            host=proxy.host,
            port=proxy.port,
            method=method,
            avg_resp_time=proxy.avg_resp_time,
            error_rate=proxy.error_rate,
            errors=proxy.stat['errors'],
            num_requests=0,  # Our reference of num_requests differs from ProxyBroker
            schemes=proxy.schemes,
        )

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
    def stat(self):
        # This is from ProxyBroker model, we probably don't need this
        # anymore.
        return {'requests': self.num_requests, 'errors': self.errors}

    def update_time(self):
        self.last_used = datetime.now()

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
    old_proxy: RequestProxy
    new_proxy: RequestProxy
    diff: List[ProxyDifference] = field(init=False)

    def __post_init__(self):
        self.diff = []

    def add(self, attr, old, new):
        diff = ProxyDifference(attr=attr, old_value=old, new_value=new)
        self.diff.append(diff)

    @property
    def none(self):
        return len(self.diff) == 0

    def __str__(self):
        strings = [str(d) for d in self.diff]
        return ', '.join(strings)
