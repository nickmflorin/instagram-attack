# -*- coding: utf-8 -*-
from collections import deque
from datetime import datetime
from dataclasses import dataclass, field
from dacite import from_dict

import functools
import math

import tortoise
from tortoise import fields
from tortoise.models import Model

from instattack.config import settings, config
from instattack.lib import logger

from instattack.app.exceptions import ConfigError, ProxyMaxTimeoutError

from .evaluation import evaluate
from .mixins import HumanizedMetrics, DerivedMetrics, allow_exception_input


log = logger.get(__name__, subname='Proxy')


@dataclass
class ProxyResult:

    date: datetime = field(init=False)
    error: str = None
    status_code: int = None

    def __post_init__(self):
        self.date = datetime.now()

    @property
    def confirmed(self):
        return self.error is None

    @classmethod
    def from_dict(cls, data):
        data['date'] = datetime.strptime(data['date'], "%m/%d/%Y, %H:%M:%S")
        return from_dict(data_class=cls, data=data)

    @property
    def was_timeout_error(self):
        if self.error is not None:
            if self.error in settings.TIMEOUT_ERRORS:
                return True
        return False

    def __str__(self):
        if self.error:
            return self.error
        return 'Success'

    @property
    def __dict__(self):
        data = {}
        data['date'] = self.date.strftime("%m/%d/%Y, %H:%M:%S")
        if self.error:
            data['error'] = self.error
        if self.status_code:
            data['status_code'] = self.status_code
        return data


class Proxy(Model, HumanizedMetrics, DerivedMetrics):

    id = fields.IntField(pk=True)
    host = fields.CharField(max_length=30)
    port = fields.IntField()
    avg_resp_time = fields.FloatField()
    last_used = fields.DatetimeField(null=True)
    date_added = fields.DatetimeField(auto_now_add=True)
    history = fields.JSONField(default=[])

    class Meta:
        unique_together = ('host', 'port')

    def __init__(self, *args, **kwargs) -> None:
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        super(Proxy, self).__init__(*args, **kwargs)

        self.history = deque(sorted(
            [ProxyResult.from_dict(data) for data in self.history],
            key=lambda x: x.date,
        ))

        # Temporary Sanity Check
        if len(self.history) > 1:
            assert self.history[0].date <= self.history[-1].date

        self.active_history = deque([])
        self.queue_id = None

        timeout_config = config['proxies']['timeouts']
        self._timeouts = {
            'too_many_requests': {
                'start': timeout_config['too_many_requests']['start'],
                'count': 0,
                # Coefficient Not Currently Used
                'coefficient': timeout_config['too_many_requests']['coefficient'],
                'increment': timeout_config['too_many_requests']['increment'],
                'max': timeout_config['too_many_requests']['max'],
            },
            'too_many_open_connections': {
                'start': timeout_config['too_many_open_connections']['start'],
                'count': 0,
                # Coefficient Not Currently Used
                'coefficient': timeout_config['too_many_open_connections']['coefficient'],
                'increment': timeout_config['too_many_requests']['increment'],
                'max': timeout_config['too_many_open_connections']['max'],
            },
        }

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

    def update_time(self):
        self.last_used = datetime.now()

    @property
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return 0.0

    def priority(self, count):
        """
        We do not need the confirmed fields since they already are factored
        in based on the separate queues.

        [!] IMPORTANT:
        -------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """
        PROXY_PRIORITY_VALUES = []
        raw_priority_values = config['pool']['priority']

        for priority in raw_priority_values:
            if not hasattr(self, priority[1]):
                raise ConfigError("Invalid priority value %s." % priority[1])

            PROXY_PRIORITY_VALUES.append((
                int(priority[0]), getattr(self, priority[1])
            ))

        return tuple([
            field[0] * field[1]
            for field in PROXY_PRIORITY_VALUES
        ] + [count])

    @allow_exception_input
    def reset_timeout(self, err):
        self._timeouts[err]['count'] = 0

    def reset_timeouts(self):
        for err in settings.TIMEOUT_ERRORS:
            self.reset_timeout(err)

    @allow_exception_input
    def increment_timeout(self, err):
        log.debug('Incrementing %s Timeout Count to %s' % (
            err, self.timeout_count(err) + 1))
        self._timeouts[err]['count'] += 1

        if self.timeout_exceeds_max(err):
            log.warning(f'Proxy Timeout {self.timeout(err)} Exceeded Max {self.timeout_max(err)}')
            # raise ProxyMaxTimeoutError(err, self.timeout(err))

    @allow_exception_input
    def timeout_exceeds_max(self, *args):
        for err in args:
            timeout = self.timeout(err)
            max_timeout = self.timeout_max(err)
            if timeout > max_timeout:
                return True

    def add_error(self, exc):

        result = ProxyResult(
            error=exc.__subtype__,
            status_code=exc.status_code,
        )
        self.active_history.append(result)
        self.history.append(result)

    def add_success(self):
        result = ProxyResult()
        self.active_history.append(result)
        self.history.append(result)

    def error_rate(self, active=False):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        failed = self.num_requests(active=active, fail=True)
        total = self.num_requests(active=active)

        if total >= self.error_rate_horizon:
            return float(failed) / float(total)
        return 0.0

    @property
    def error_rate_horizon(self):
        """
        The sufficicent number of requests that are required for thte error-rate
        to be a non-zero value.
        """
        err_rate = config['proxies']['limits'].get('error_rate', {})
        return err_rate.get('horizon')

    def last_error(self, active=False):
        errors = self.errors(active=active)
        if len(errors) != 0:
            return errors[-1]
        return None

    def last_request(self, active=False):
        requests = self._history(active=active)
        if len(requests) != 0:
            return requests[-1]
        return None

    def evaluate_for_pool(self):
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
        return evaluate(self)

    @classmethod
    async def find_for_proxybroker(cls, broker_proxy):
        """
        Finds the related Proxy model for a given proxybroker Proxy model
        and returns the instance if present.
        """
        try:
            return await cls.get(
                host=broker_proxy.host,
                port=broker_proxy.port,
            )
        except tortoise.exceptions.DoesNotExist:
            return None
        except tortoise.exceptions.MultipleObjectsReturned:
            all_proxies = await cls.filter(
                host=broker_proxy.host,
                port=broker_proxy.port
            ).all()
            log.warning(
                f'Found {len(all_proxies)} Duplicate Proxies for '
                f'{broker_proxy.host} - {broker_proxy.port}.',
                extra={
                    'other': f'Deleting {len(all_proxies) - 1} Duplicates...'
                }
            )

            all_proxies = sorted(all_proxies, key=lambda x: x.date_added)
            for proxy in all_proxies[1:]:
                log.warning('Deleting Duplicate Proxy', extra={'proxy': proxy})
                await proxy.delete()

            return all_proxies[0]

    @classmethod
    def translate_proxybroker_history(cls, broker_proxy):
        errors = []
        for err, count in broker_proxy.stat['errors'].__dict__.items():
            if err in settings.PROXY_BROKER_ERROR_TRANSLATION:
                for i in range(count):
                    errors.append(ProxyResult(
                        error=settings.PROXY_BROKER_ERROR_TRANSLATION[err]))
            else:
                log.warning(f'Unexpected Proxy Broker Error: {err}.')
        return errors

    async def update_from_proxybroker(self, broker_proxy):

        history = self.translate_proxybroker_history(broker_proxy)
        self.history.extend(history)
        self.active_history.extend(history)

        # Only do this for as long as we are not measuring this value ourselves.
        # When we start measuring ourselves, we are not going to want to
        # overwrite it.
        self.avg_resp_time = broker_proxy.avg_resp_time
        await self.save()

    @classmethod
    async def create_from_proxybroker(cls, broker_proxy):
        return await cls.create(
            host=broker_proxy.host,
            port=broker_proxy.port,
            avg_resp_time=broker_proxy.avg_resp_time,
            history=cls.translate_proxybroker_history(broker_proxy),
        )

    @classmethod
    async def update_or_create_from_proxybroker(cls, broker_proxy):
        """
        Finds the possibly related Proxy instance for a proxybroker Proxy instance
        and updates it with relevant info from the proxybroker instance if
        present, otherwise it will create a new Proxy instance using the information
        from the proxybroker instance.
        """
        proxy = await cls.find_for_proxybroker(broker_proxy)
        if proxy:
            await proxy.update_from_proxybroker(broker_proxy)
            return proxy, False
        else:
            proxy = await cls.create_from_proxybroker(broker_proxy)
            return proxy, True

    async def save(self, *args, **kwargs):
        self.history = [data.__dict__ for data in self.history]
        await super(Proxy, self).save()
