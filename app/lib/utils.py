from __future__ import absolute_import

from app.lib import exceptions


__all__ = ('ensure_safe_http', 'update_proxy_if_provided')


def ensure_safe_http(func):
    def wrapper(instance, *args, **kwargs):
        if not instance.proxies:
            raise exceptions.MissingProxyException()
        return func(instance, *args, **kwargs)
    return wrapper


def update_proxy_if_provided(func):
    def wrapper(instance, *args, **kwargs):
        if kwargs.get('proxy'):
            instance.update_proxy(kwargs['proxy'])
        return func(instance, *args, **kwargs)
    return wrapper
