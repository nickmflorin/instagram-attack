# -*- coding: utf-8 -*-
from datetime import datetime

from tortoise import fields
from tortoise.models import Model

from instattack import logger, settings
from instattack.src.base import ModelMixin

from .err_handler import ErrorHandlerMixin
from .proxybroker import ProxyBrokerMixin


class Proxy(Model, ModelMixin, ProxyBrokerMixin, ErrorHandlerMixin):

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

    async def handle_success(self, save=True):
        self.num_requests += 1

    def reset(self):
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        self.num_active_requests = 0
        self.active_errors = {'all': {}}

    def priority(self, count):
        from .score import priority
        return priority(self, count)

    def update_time(self):
        self.last_used = datetime.now()

    async def save(self, *args, **kwargs):
        """
        We don't want to reset num_active_requests and active_errors here
        because we save the proxy intermittedly throughout the operation.
        """
        log = logger.get_async(__name__, subname='save')

        if not self.errors:
            self.errors = {'all': {}}
        elif type(self.errors) is dict and 'all' not in self.errors:
            self.errors = {'all': self.errors}

        for key, val in self.errors['all'].items():
            if key not in settings.ERROR_TRANSLATION.values():
                if key not in settings.ERROR_TRANSLATION.keys():
                    log.error(f'Invalid Error Name: {key}... Removing Error')
                else:
                    translated = settings.ERROR_TRANSLATION[key]
                    log.error(f'Unrecognized Error Name: {key}... Translating to {translated}.')

                    self.errors[translated] = self.errors[key]
                    del self.errors[key]

        await super(Proxy, self).save(*args, **kwargs)
