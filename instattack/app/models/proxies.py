# -*- coding: utf-8 -*-
from datetime import datetime

import tortoise
from tortoise import fields
from tortoise.models import Model

from instattack.config import settings, config
from instattack.lib import logger

from .evaluation import evaluate
from .mixins import HumanizedMetrics


class Proxy(Model, HumanizedMetrics):

    id = fields.IntField(pk=True)
    host = fields.CharField(max_length=30)
    port = fields.IntField()
    avg_resp_time = fields.FloatField()
    last_used = fields.DatetimeField(null=True)
    date_added = fields.DatetimeField(auto_now_add=True)

    errors = fields.JSONField(default={})
    num_requests = fields.IntField(default=0)
    num_successful_requests = fields.IntField(default=0)
    num_failed_requests = fields.IntField(default=0)

    confirmed = fields.BooleanField(default=False)
    last_request_confirmed = fields.BooleanField(default=False)
    last_error = fields.CharField(max_length=15, null=True)

    class Meta:
        unique_together = ('host', 'port')

    identifier_fields = ('host', 'port')

    TIMEOUT_ERRORS = ('too_many_requests', 'too_many_open_connections')

    def __init__(self, *args, **kwargs) -> None:
        """
        Reset values that are meant to only be used during time proxy is active
        and in pool.
        """
        super(Proxy, self).__init__(*args, **kwargs)

        self.num_active_requests = 0
        self.num_active_failed_requests = 0
        self.num_active_successful_requests = 0

        self.active_errors = {}

        # This will be the ACTUAL error.
        self.last_active_error = None

        # Referenced from Configuration
        self._timeouts = {
            'too_many_requests': (
                config['proxies']['timeouts']['too_many_requests']['start']),
            'too_many_open_connections': (
                config['proxies']['timeouts']['too_many_open_connections']['start'])
        }
        self._timeout_increments = {
            'too_many_requests': (
                config['proxies']['timeouts']['too_many_requests']['increment']),
            'too_many_open_connections': (
                config['proxies']['timeouts']['too_many_open_connections']['increment'])
        }

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

    def update_time(self):
        self.last_used = datetime.now()

    @property
    def time_since_used(self):
        if self.last_used:
            delta = datetime.now() - self.last_used
            return delta.total_seconds()
        return 0.0

    @property
    def priority_values(self):
        # We do not need the confirmed fields since they already are factored
        # in based on the separate queues.
        PROXY_PRIORITY_VALUES = (
            (-1, self.num_active_successful_requests),
            (1, self.active_error_rate),
            (-1, self.num_successful_requests),
            (1, self.historical_error_rate),
            (1, self.avg_resp_time),
        )

        return [
            field[0] * field[1]
            for field in PROXY_PRIORITY_VALUES
        ]

    def priority(self, count):
        priority = self.priority_values[:]
        priority.append(count)
        return tuple(priority)

    def timeout(self, err):
        if isinstance(err, Exception):
            err = err.__subtype__
        return self._timeouts[err]

    def timeout_increment(self, err):
        if isinstance(err, Exception):
            err = err.__subtype__
        return self._timeout_increments[err]

    def increment_timeout(self, err):
        if isinstance(err, Exception):
            err = err.__subtype__
        self._timeouts[err] += self.timeout_increment(err)

    def note_success(self):
        self.num_requests += 1
        self.num_active_requests += 1
        self.num_successful_requests += 1
        self.num_active_successful_requests += 1
        self.last_request_confirmed = True
        self.confirmed = True

    def note_failure(self):
        self.num_requests += 1
        self.num_active_requests += 1
        self.num_failed_requests += 1
        self.num_active_failed_requests += 1
        self.last_request_confirmed = False

    def set_recent_error(self, exc, historical=True, active=True):
        # For active errors, since we are not saving those to DB, we store the
        # actual error class.
        if active:
            self.last_active_error = exc
        if historical:
            self.last_error = exc.__subtype__

    def add_error(self, exc, count=1, historical=True, active=True):
        # For active errors, since we are not saving those to DB, we use the
        # actual error class.
        if active:
            self.active_errors.setdefault(exc, 0)
            self.active_errors[exc] += count

        if historical:
            self.errors.setdefault(exc.__subtype__, 0)
            self.errors[exc.__subtype__] += count

    def include_errors(self, errors):
        for key, val in errors.items():
            self.add_error(
                key,
                count=val,
                active=True,
                historical=True,
            )

    @property
    def error_rate_horizon(self):
        err_rate = config['proxies']['limits'].get('error_rate', {})
        return err_rate.get('horizon')

    @property
    def active_error_rate(self):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        if self.num_active_requests >= self.error_rate_horizon:
            return float(self.num_active_failed_requests) / float(self.num_active_requests)
        return 0.0

    @property
    def historical_error_rate(self):
        """
        Counts the error_rate as 0.0 until there are a sufficient number of
        requests.
        """
        if self.num_requests >= self.error_rate_horizon:
            return float(self.num_failed_requests) / float(self.num_requests)
        return 0.0

    def _num_active_errors(self, *args):

        # Convert Errors to String Representation
        search_errors = []
        _search_errors = list(args)
        for err in _search_errors:
            if isinstance(err, Exception):
                search_errors.append(err.__subtype__)
            else:
                search_errors.append(err)

        ct = 0
        for err, count in self.active_errors.items():
            if not search_errors:
                ct += count
            else:
                # This line is the difference between _num_historical_errors and
                # _num_active_errors.
                if err.__subtype__ in search_errors:
                    ct += count
        return ct

    def _num_historical_errors(self, *args):

        # Convert Errors to String Representation
        _search_errors = list(args)
        search_errors = []
        for err in _search_errors:
            if isinstance(err, Exception):
                search_errors.append(err.__subtype__)
            else:
                search_errors.append(err)

        ct = 0
        for err, count in self.active_errors.items():
            if not search_errors:
                ct += count
            else:
                # This line is the difference between _num_historical_errors and
                # _num_active_errors.
                if err in search_errors:
                    ct += count
        return ct

    def _num_errors(self, *args, active=False, historical=True):
        """
        For active errors, we store the actual error class in the dictionary,
        whereas for historical errors, we store the __subtype__ string.
        """
        count = 0
        if active:
            count += self._num_active_errors(*args)
        if historical:
            count += self._num_historical_errors(*args)
        return count

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

    def hold(self):
        """
        If the Proxy just resulted in a num_requests error, we don't want to
        put back in the Pool immediately because it will have a high priority
        and will likely slow down the retrieval of subsequent proxies because
        it cannot be used just yet.

        Instead, we put in an array to hold onto until it is ready to be used.
        """
        for err in self.TIMEOUT_ERRORS:
            if self.last_active_error and self.last_active_error.__subtype__ == err:
                timeout = self.timeout(err)
                if self.time_since_used < timeout:
                    return True

        return False

    @classmethod
    async def find_for_proxybroker(cls, broker_proxy):
        """
        Finds the related Proxy model for a given proxybroker Proxy model
        and returns the instance if present.
        """
        log = logger.get_async(__name__, subname='find_for_proxybroker')

        try:
            return await cls.get(
                host=broker_proxy.host,
                port=broker_proxy.port,
            )
        except tortoise.exceptions.DoesNotExist:
            return None
        except tortoise.exceptions.MultipleObjectsReturned:
            all_proxies = await cls.filter(host=broker_proxy.host, port=broker_proxy.port).all()
            await log.warning(
                f'Found {len(all_proxies)} Duplicate Proxies for '
                f'{broker_proxy.host} - {broker_proxy.port}.',
                extra={
                    'other': f'Deleting {len(all_proxies) - 1} Duplicates...'
                }
            )

            all_proxies = sorted(all_proxies, key=lambda x: x.date_added)
            for proxy in all_proxies[1:]:
                await log.warning('Deleting Duplicate Proxy', extra={'proxy': proxy})
                await proxy.delete()

            return all_proxies[0]

    @classmethod
    def translate_proxybroker_errors(cls, broker_proxy):
        log = logger.get_sync(__name__, subname='translate_proxybroker_errors')

        errors = {}
        for err, count in broker_proxy.stat['errors'].__dict__.items():
            if err in settings.PROXY_BROKER_ERROR_TRANSLATION:
                errors[settings.PROXY_BROKER_ERROR_TRANSLATION[err]] = count
            else:
                log.warning(f'Unexpected Proxy Broker Error: {err}.')
                errors[err] = count
        return errors

    async def update_from_proxybroker(self, broker_proxy, save=False):
        errors = self.translate_proxybroker_errors(broker_proxy)

        self.include_errors(errors)

        self.num_requests += broker_proxy.stat['requests']
        self.num_active_requests += broker_proxy.stat['requests']

        # Only do this for as long as we are not measuring this value ourselves.
        # When we start measuring ourselves, we are not going to want to
        # overwrite it.
        self.avg_resp_time = broker_proxy.avg_resp_time
        if save:
            await self.save()

    @classmethod
    async def create_from_proxybroker(cls, broker_proxy, save=False):

        proxy = cls(
            host=broker_proxy.host,
            port=broker_proxy.port,
            avg_resp_time=broker_proxy.avg_resp_time,
            errors=cls.translate_proxybroker_errors(broker_proxy),
            num_requests=broker_proxy.stat['requests'],
        )
        if save:
            await proxy.save()
        return proxy

    @classmethod
    async def update_or_create_from_proxybroker(cls, broker_proxy, save=False):
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
        proxy = await cls.find_for_proxybroker(broker_proxy)
        if proxy:
            await proxy.update_from_proxybroker(broker_proxy, save=save)
            return proxy, False
        else:
            proxy = await cls.create_from_proxybroker(broker_proxy, save=save)
            return proxy, True

    async def save(self, *args, **kwargs):
        if self.num_successful_requests + self.num_failed_requests != self.num_requests:
            raise tortoise.exceptions.IntegrityError('Inconsistent Request Counts')
        super(Proxy, self).save(*args, **kwargs)
