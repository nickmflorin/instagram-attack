# -*- coding: utf-8 -*-
from __future__ import absolute_import

from collections import Counter

from dataclasses import dataclass, field
from datetime import datetime

from instattack import validate_method


@dataclass
class RequestProxy:

    host: str
    port: int
    method: str
    avg_resp_time: float
    error_rate: float
    errors: field(default_factory=Counter)  # Not Currently Used

    confirmed: bool = False
    last_used: datetime = None
    num_requests: int = 0  # Not Currently Used
    schemes: tuple = ()

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return (self.host, self.port, self.method) == (other.host, other.port, other.method)

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
