import functools

from contextlib import ContextDecorator


class starting_context(ContextDecorator):

    def __init__(self, instance, name=None):
        self.instance = instance
        self.name = name or getattr(instance, 'name', None) or instance.__class__.__name__

    def __enter__(self):
        self.instance.log.start(f'Starting {self.name}')
        return self

    def __exit__(self, *exc):
        return False


class stopping_context(ContextDecorator):

    def __init__(self, instance, name=None):
        self.instance = instance
        self.name = name or getattr(instance, 'name', None) or instance.__class__.__name__

    def __enter__(self):
        self.instance.log.start(f'Stopping {self.name}')
        return self

    def __exit__(self, *exc):
        return False


def starting(*args):

    def _starting(func, name=None):

        def _wrapped(instance, *args, **kwargs):
            log_name = name or instance.name
            instance.log.start(f'Starting {log_name}')
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
            instance.log.start(f'Stopping {log_name}')
            return func(instance, *args, **kwargs)

        return _wrapped

    if len(args) == 1 and callable(args[0]):
        return _stopping(args[0], name=None)
    else:
        return functools.partial(_stopping, name=args[0])
