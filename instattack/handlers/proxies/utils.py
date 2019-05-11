import asyncio

from instattack.lib import AppLogger, validate_method

from instattack.models import Proxy


log = AppLogger(__file__)


__all__ = ('stream_proxies', )


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
    log.info(f'Created {method} {num_created} Proxies')

    updated = [res for res in results if res[0]]
    num_updated = len(updated)
    log.info(f'Updated {method} {num_updated} Proxies')
