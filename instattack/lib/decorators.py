import functools

from contextlib import ContextDecorator


class starting_context(ContextDecorator):

    def __init__(self, instance, name=None, subname=None):
        self.instance = instance
        self.name = name or getattr(instance, 'name', None) or instance.__class__.__name__
        self.subname = subname

    def __enter__(self):
        logger = self.instance.log
        if self.subname:
            logger = logger.sublogger(self.subname)
        logger.start(f'Starting {self.name}', frame_correction=1)
        return self

    def __exit__(self, *exc):
        return False


class stopping_context(ContextDecorator):

    def __init__(self, instance, name=None):
        self.instance = instance
        self.name = name or getattr(instance, 'name', None) or instance.__class__.__name__

    def __enter__(self):
        logger = self.instance.log
        if self.subname:
            logger = logger.sublogger(self.subname)
        logger.stop(f'Stopping {self.name}', frame_correction=1)
        return self

    def __exit__(self, *exc):
        return False


def starting(*args):

    def _starting(func, name=None):

        def _wrapped(instance, *args, **kwargs):
            log_name = name or instance.name
            sublog = instance.log.sublogger(func.__name__)
            sublog.start(f'Starting {log_name}', frame_correction=1)
            return func(instance, *args, **kwargs)

        return _wrapped

    if len(args) == 1 and callable(args[0]):
        return _starting(args[0], name=None)
    else:
        return functools.partial(_starting, name=args[0])


def stopping(*args):

    def _stopping(func, name=None):

        def _wrapped(instance, *args, **kwargs):
            log_name = name or instance.name
            sublog = instance.log.sublogger(func.__name__)
            sublog.stop(f'Stopping {log_name}', frame_correction=1)
            return func(instance, *args, **kwargs)

        return _wrapped

    if len(args) == 1 and callable(args[0]):
        return _stopping(args[0], name=None)
    else:
        return functools.partial(_stopping, name=args[0])
