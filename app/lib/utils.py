from __future__ import absolute_import

from collections import Iterable
import logging


__all__ = ('auto_logger', 'ensure_iterable', 'get_token_from_cookies')


def ensure_iterable(arg):
    if isinstance(arg, str):
        return [arg]
    elif not isinstance(arg, Iterable):
        return [arg]
    return arg


def auto_logger(*args, **kwargs):

    def _auto_logger(func, show_running=True):
        def wrapper(instance, *args, **kwargs):
            logger_name = instance.__loggers__[func.__name__]
            log = logging.getLogger(logger_name)

            if show_running:
                log.info("Running...")

            args = args + (log, )
            return func(instance, *args, **kwargs)
        return wrapper

    if len(args) == 1 and callable(args[0]):
        return _auto_logger(args[0], **kwargs)
    else:
        return _auto_logger


def get_token_from_cookies(cookies):
    cookie = cookies.get('csrftoken')
    if cookie:
        return cookie.value


def get_cookies_from_response(response):
    return response.cookies


def get_token_from_response(response):
    cookies = get_cookies_from_response(response)
    if cookies:
        return get_token_from_cookies(cookies)
