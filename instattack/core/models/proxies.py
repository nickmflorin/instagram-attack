# -*- coding: utf-8 -*-
from datetime import datetime
from dataclasses import dataclass, field
from dacite import from_dict

import functools
import math

import tortoise
from tortoise import fields
from tortoise.models import Model

from instattack.config import constants, config
from instattack.lib import logger

from instattack.core.exceptions import ConfigError, ProxyMaxTimeoutError

from .evaluation import evaluate
from .mixins import ProxyMetrics, allow_exception_input


log = logger.get(__name__, subname='Proxy')


@dataclass
class ProxyRequest:

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
            if self.error in constants.TIMEOUT_ERRORS:
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


class Proxy(Model, ProxyMetrics):

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

        self.history = sorted(
            [ProxyRequest.from_dict(data) for data in self.history],
            key=lambda x: x.date,
        )

        # Temporary Sanity Check
        if len(self.history) > 1:
            assert self.history[0].date <= self.history[-1].date

        self.active_history = []
        self.queue_id = None

        timeout_config = config['proxies']['pool']['timeouts']
        self._timeouts = {
            'too_many_requests': {
                'start': timeout_config['too_many_requests']['start'],
                'count': 0,
                'increment': timeout_config['too_many_requests']['increment'],
                'max': timeout_config['too_many_requests']['max'],
            },
            'too_many_open_connections': {
                'start': timeout_config['too_many_open_connections']['start'],
                'count': 0,
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

    @allow_exception_input
    def reset_timeout(self, err):
        self._timeouts[err]['count'] = 0

    def reset_timeouts(self):
        for err in constants.TIMEOUT_ERRORS:
            self.reset_timeout(err)

    @allow_exception_input
    def increment_timeout(self, err):
        current_timeout = self.timeout(err)
        self._timeouts[err]['count'] += 1
        new_timeout = self.timeout(err)

        log.debug(f'Incrementing Timeout Count from {current_timeout} to {new_timeout}', extra={
            'proxy': self,
        })

        if self.timeout_exceeds_max(err):
            log.warning(f'Proxy Timeout {self.timeout(err)} Exceeded Max {self.timeout_max(err)}')
            raise ProxyMaxTimeoutError(err, self.timeout(err))

    @allow_exception_input
    def timeout_exceeds_max(self, *args):
        for err in args:
            timeout = self.timeout(err)
            max_timeout = self.timeout_max(err)
            if timeout > max_timeout:
                return True

    def add_failed_request(self, req):
        self.active_history.append(req)
        self.history.append(req)

        # Probably Not Necessary but Just in Case
        self.history = sorted(self.history, key=lambda x: x.date)
        self.active_history = sorted(self.active_history, key=lambda x: x.date)

    def add_successful_request(self, req):
        self.active_history.append(req)
        self.history.append(req)

        # Probably Not Necessary but Just in Case
        self.history = sorted(self.history, key=lambda x: x.date)
        self.active_history = sorted(self.active_history, key=lambda x: x.date)

    def confirmed(self):
        """
        [x] TODO:
        --------
        Should we set configuration defaults for the threshold, horizon and
        threshold in horizon parameters?

        Should we allow whether or not we are looking at active or historical
        horizons to be specified in config?
        """
        confirmed_config = config['proxies']['pool'].get('confirmation', {})

        # Should We Set Defaults for These?
        threshold = confirmed_config.get('threshold')
        horizon = confirmed_config.get('horizon')
        threshold_in_horizon = confirmed_config.get('threshold_in_horizon')

        if threshold:
            if not self.confirmed_over_threshold(threshold):
                return False

        if horizon:
            if threshold_in_horizon:
                if not self.confirmed_over(
                    threshold=threshold_in_horizon,
                    horizon=horizon,
                ):
                    return False
            else:
                if not self.confirmed_in_horizon(horizon=horizon):
                    return False

        return True

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
            if err in constants.PROXY_BROKER_ERROR_TRANSLATION:
                for i in range(count):
                    errors.append(ProxyResult(
                        error=constants.PROXY_BROKER_ERROR_TRANSLATION[err]))
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
