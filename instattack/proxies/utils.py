from __future__ import absolute_import


def filter_proxy(proxy, max_error_rate=None, max_resp_time=None):
    if max_error_rate and proxy.error_rate > max_error_rate:
        return (None, 'max_error_rate')

    if max_resp_time and proxy.avg_resp_time > max_resp_time:
        return (None, 'max_resp_time')
    return (proxy, None)


def filter_proxies(proxies, max_error_rate=None, max_resp_time=None):
    return [
        filtered_proxy[0] for filtered_proxy in [
            filter_proxy(proxy, max_error_rate=max_error_rate, max_resp_time=max_resp_time)
            for proxy in proxies
        ] if filtered_proxy[0] is not None
    ]
