# Temporary, just in case we want to put back in.
LOG_COMPLETION = False


def starting(func):
    def _wrapped(instance, *args, **kwargs):
        instance.log.start(f'Starting {instance.name}')
        result = func(instance, *args, **kwargs)
        if LOG_COMPLETION:
            instance.log.complete(f'{instance.name} Was Successfully Started')
        return result
    return _wrapped


def stopping(func):
    def _wrapped(instance, *args, **kwargs):
        instance.log.start(f'Stopping {instance.name}')
        result = func(instance, *args, **kwargs)
        if LOG_COMPLETION:
            instance.log.complete(f'{instance.name} Was Successfully Stopped')
        return result
    return _wrapped
