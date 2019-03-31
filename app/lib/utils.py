from __future__ import absolute_import

import logging


__all__ = ('auto_logger')


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
