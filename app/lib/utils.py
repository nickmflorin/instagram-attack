from __future__ import absolute_import

from collections import Iterable
import logging

import app.lib.exceptions as exceptions


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


def get_token_from_cookies(cookies, proxy=None, strict=False):
    cookie = cookies.get('csrftoken')
    if not cookie:
        if strict:
            raise exceptions.TokenNotInResponse(proxy=proxy)
        else:
            return None
    token = cookie.value
    if not token:
        if strict:
            raise exceptions.TokenNotInResponse(proxy=proxy)
        else:
            return None
    return token


def get_cookies_from_response(response, proxy=None, strict=False):
    if not response.cookies:
        if strict:
            raise exceptions.CookiesNotInResponse(proxy=proxy)
        else:
            return None
    return response.cookies


def get_token_from_response(response, proxy=None, strict=False):
    try:
        cookies = get_cookies_from_response(response, proxy=proxy, strict=strict)
    except exceptions.CookiesNotInResponse:
        raise exceptions.TokenNotInResponse(proxy=proxy)
    else:
        return get_token_from_cookies(cookies)
