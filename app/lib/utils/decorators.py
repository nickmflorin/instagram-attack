from __future__ import absolute_import

import functools
import logging


__all__ = ('auto_logger', )


def create_auto_log(func, name=None, level=None):
    from app.lib.logging import AppLogger

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
