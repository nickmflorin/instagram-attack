import asyncio

from instattack.lib.utils import validate_method
from instattack.lib.logger import AppLogger

from .models import Proxy


log = AppLogger(__file__)


__all__ = ('stream_proxies', 'PoolNotifier', )


async def stream_proxies(method, limit=None):

    method = validate_method(method)
    async for proxy in Proxy.filter(method=method).all():
        yield proxy


async def update_or_create_proxies(method, proxies, overwrite=False):

    if overwrite:
        raise NotImplementedError(
            'Not currently supporting overwrite capability.')

    async def update_or_create(proxy):

        saved = await Proxy.filter(
            host=proxy.host,
            port=proxy.port,
            method=method,
        ).first()

        if not saved:
            saved = await Proxy.create(
                host=proxy.host,
                port=proxy.port,
                method=method,
                # Do we want to maybe also store num_requests or anything like that?
                # We have to reset those on initialization anyways...
                avg_resp_time=proxy.avg_resp_time,
                error_rate=proxy.error_rate,
            )
            return False, True, None
        else:
            differences = saved.compare(proxy, return_difference=True)
            if not differences:
                return False, False, None

            await Proxy.filter(
                host=proxy.host,
                port=proxy.port,
                method=method,
            ).update(
                # Do we want to maybe also store num_requests or anything like that?
                # We have to reset those on initialization anyways...
                avg_resp_time=proxy.avg_resp_time,
                error_rate=proxy.error_rate,
            )
            return True, False, differences

    tasks = []
    for proxy in proxies:
        task = asyncio.create_task(update_or_create(proxy))
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    num_created = len([res for res in results if res[1]])
    log.notice(f'Created {method} {num_created} Proxies')

    updated = [res for res in results if res[0]]
    num_updated = len(updated)
    log.notice(f'Updated {method} {num_updated} Proxies')


class PoolNotifier(object):

    __actions__ = {
        'add': 'Adding {type} Proxy to Pool',
        'update': 'Updating {type} Proxy in Pool',
        'retrieved_pool': 'Retrieved {type} Proxy from Pool',
        'cannot_add': 'Cannot Add {type} Proxy to Pool',
        'remove': 'Removing {type} Proxy from Pool'
    }

    def __init__(self, pool, log_saved_proxies=False, log_proxies=False):
        self.pool = pool
        self.log_saved_proxies = log_saved_proxies
        self.log_proxies = log_proxies

    def __call__(self, proxy, msg=None, action=None, force=False, level='debug', **kwargs):
        if self.should_notify(proxy, level=level, force=force):
            msg, extra = self.notification(proxy, msg=msg, action=action, **kwargs)
            meth = getattr(self.pool.log, level)
            meth(msg, frame_correction=1, extra=extra)

    def should_notify(self, proxy, level='debug', force=False):
        if (level == 'debug' and not force and
            (proxy.id and self.log_saved_proxies) or
                (not proxy.id and self.log_proxies)):
            return True
        return False

    def notification(self, proxy, msg=None, action=None, **kwargs):
        extra = {'proxy': proxy}
        extra.update(**kwargs)

        if not msg:
            msg = self.__actions__[action]
            if proxy.id:
                return msg.format(type='Saved'), extra
            return msg.format(type='Broker'), extra
        return msg, extra
