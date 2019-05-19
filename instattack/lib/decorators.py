import asyncio
import functools

import inspect

from instattack import logger


def starting(*args):

    def _starting(func, name=None):

        def _wrapped(instance, *args, **kwargs):
            stack_info = inspect.stack()

            log_name = name or instance.name
            is_async = asyncio.iscoroutinefunction(func)
            if is_async:
                log = logger.get_async(log_name, subname=func.__name__)
            else:
                log = logger.get_sync(log_name, subname=func.__name__)

            log.start(f'Starting {log_name}', stack_info=stack_info)
            if is_async:
                asyncio.create_task(log.shutdown())
            return func(instance, *args, **kwargs)

        return _wrapped

    if len(args) == 1 and callable(args[0]):
        return _starting(args[0], name=None)
    else:
        return functools.partial(_starting, name=args[0])


def stopping(*args):

    def _stopping(func, name=None):

        def _wrapped(instance, *args, **kwargs):
            stack_info = inspect.stack()

            log_name = name or instance.name
            is_async = asyncio.iscoroutinefunction(func)
            if is_async:
                log = logger.get_async(log_name, subname=func.__name__)
            else:
                log = logger.get_sync(log_name, subname=func.__name__)

            log.start(f'Stopping {log_name}', stack_info=stack_info)
            if is_async:
                asyncio.create_task(log.shutdown())
            return func(instance, *args, **kwargs)

        return _wrapped

    if len(args) == 1 and callable(args[0]):
        return _stopping(args[0], name=None)
    else:
        return functools.partial(_stopping, name=args[0])
