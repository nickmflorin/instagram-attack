# -*- coding: utf-8 -*-
from datetime import datetime

from tortoise import fields
from tortoise.models import Model

from .evaluation import evaluate, ProxyEvaluation
from .mixins import ErrorHandlerMixin, ProxyBrokerMixin


PROXY_PRIORITY_FIELDS = (
    (1, 'flattened_error_rate'),
    (-1, 'num_active_successful_requests'),
    (-1, 'num_successful_requests'),
    (1, 'avg_resp_time'),
)


class Proxy(Model, ProxyBrokerMixin, ErrorHandlerMixin):

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

    def reset(self):
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        self.num_active_requests = 0
        self.active_errors = {'all': {}}

    def update_time(self):
        self.last_used = datetime.now()

    @property
    def priority_values(self):
        return [
            field[0] * getattr(self, field[1])
            for field in PROXY_PRIORITY_FIELDS
        ]

    def priority(self, count):
        priority = self.priority_values
        priority.append(count)
        return tuple(priority)

    def evaluate_for_pool(self, config):
        """
        Called before a proxy is put into the Pool.

        Allows us to disregard or completely ignore proxies without having
        to delete them from DB.

        [x] TODO:
        --------
        Incorporate limit on certain errors or exclusion of proxy based on certain
        errors in general.

        Make it so that we can return the evaluations and also indicate
        that it is okay or not okay for the pool.
        """
        evaluation = evaluate(self, config)
        return evaluation

    def evaluate_for_use(self, config):
        """
        Called before a proxy is returned from the Pool.  This is where we want to
        evaluate things that would not prevent a proxy from going into the pool,
        but just from being pulled out at that moment.

        This should incorporate timing aspects and things of that nature.
        Can include more custom logic indicating the desired use of the
        proxy than we can do with the priority alone.
        """

        # TODO: We should only restrict time since last used if the last request was
        # a too many request error.
        time_since_used = config['proxies']['pool']['time_between_request_timeout']

        if (self.active_errors.get('most_recent') and
                self.active_errors['most_recent'] == 'too_many_requests'):
            evaluation = evaluate(self, time_since_used=time_since_used)
            return evaluation
        else:
            return ProxyEvaluation(reasons=[])

    async def save(self, *args, **kwargs):
        """
        We don't want to reset num_active_requests and active_errors here
        because we save the proxy intermittedly throughout the operation.
        """
        if not self.errors:
            self.errors = {'all': {}}
        elif type(self.errors) is dict and 'all' not in self.errors:
            self.errors = {'all': self.errors}

        await super(Proxy, self).save(*args, **kwargs)
