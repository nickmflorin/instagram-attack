from __future__ import absolute_import

import functools
import logging

from app.lib.logging import AppLogger


__all__ = ('auto_logger', 'format_proxy', 'get_token_from_cookies',
    'get_cookies_from_response', 'get_token_from_response')


def format_proxy(proxy, scheme='http'):
    return f"{scheme}://{proxy.host}:{proxy.port}/"


def get_token_from_cookies(cookies):
    # aiohttp ClientResponse cookies have .value attribute.
    cookie = cookies.get('csrftoken')
    if cookie:
        try:
            return cookie.value
        except AttributeError:
            return cookie


def get_cookies_from_response(response):
    return response.cookies


def get_token_from_response(response):
    cookies = get_cookies_from_response(response)
    if cookies:
        return get_token_from_cookies(cookies)


def create_auto_log(func, name=None, level=None):
    name = name or func.__name__
    level = level or logging.INFO

    logging.setLoggerClass(AppLogger)
    log = logging.getLogger(name)
    log.setLevel(level)
    return log


def auto_logger(*args):

    def _auto_logger(func, name=None, level=None):
        name = name or func.__name__
        level = level or logging.INFO
        log = create_auto_log(func, name=name, level=level)

        def wrapper(instance, *args, **kwargs):
            args = args + (log, )
            return func(instance, *args, **kwargs)
        return wrapper

    if callable(args[0]):
        return _auto_logger(args[0])
    else:
        if len(args) == 1:
            return functools.partial(_auto_logger, name=args[0])
        else:
            return functools.partial(_auto_logger, name=args[0], level=args[1])
