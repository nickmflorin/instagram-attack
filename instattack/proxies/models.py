# -*- coding: utf-8 -*-
from __future__ import absolute_import

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Proxy:
    """
    TODO:
    ----

    Need to include additional information like ProxyBroker, things like
    num_times_used, an array of errors, things like that so we can more
    appropriately make decisions based on what is going on.
    """
    host: str
    port: int
    avg_resp_time: float
    error_rate: float
    is_working: bool = True
    valid: bool = False
    last_used: datetime = None

    @classmethod
    def from_broker_proxy(cls, proxy):
        return cls(
            host=proxy.host,
            port=proxy.port,
            avg_resp_time=proxy.avg_resp_time,
            error_rate=proxy.error_rate,
            is_working=proxy.is_working,
        )

    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return None

    def url(self, scheme='http'):
        return f"{scheme}://{self.host}:{self.port}/"
