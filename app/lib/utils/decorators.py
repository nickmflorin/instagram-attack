from __future__ import absolute_import

import functools
import logging
import os

__all__ = ('auto_logger', )


def create_auto_log(func, name):
    from app.lib.logging import AppLogger

    logging.setLoggerClass(AppLogger)
    log = logging.getLogger(name)
    return log


def auto_logger(*args):
    def _auto_logger(func, name=None):
        name = name or func.__name__
        log = create_auto_log(func, name)

        def wrapper(instance, *args, **kwargs):
            args = args + (log, )
            level = os.environ.get('INSTAGRAM_LEVEL', 'INFO')
            level = getattr(logging, level)
            log.setLevel(level)

            log.debug('Starting...')
            return func(instance, *args, **kwargs)
        return wrapper

    if callable(args[0]):
        return _auto_logger(args[0])
    else:
        if len(args) == 1:
            return functools.partial(_auto_logger, name=args[0])
        else:
            return functools.partial(_auto_logger, name=args[0], level=args[1])
