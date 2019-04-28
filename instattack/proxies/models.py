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
    confirmed: bool = False
    last_used: datetime = None
    times_used: int = 0

    @property
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return None

    def update_time(self):
        self.last_used = datetime.now()

    def url(self, scheme='http'):
        return f"{scheme}://{self.host}:{self.port}/"
