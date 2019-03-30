from __future__ import absolute_import

import logging

from app.lib import exceptions


__all__ = ('ensure_safe_http', 'update_proxy_if_provided', 'auto_logger')


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


def auto_logger(*args, **kwargs):

    def _auto_logger(func, **kw):
        def wrapper(instance, *args, **kwargs):
            logger_name = instance.__loggers__[func.__name__]
            log = logging.getLogger(logger_name)

            if kw.get('show_running'):
                log.info("Running...")

            args = args + (log, )
            return func(instance, *args, **kwargs)
        return wrapper

    if len(args) == 1 and callable(args[0]):
        return _auto_logger(args[0], **kwargs)
    else:
        return _auto_logger
