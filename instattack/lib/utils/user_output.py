import asyncio
import contextlib
from functools import wraps
import sys

from .yaspin import CustomYaspin


def yaspin(*args, **kwargs):
    return CustomYaspin(*args, **kwargs)


@contextlib.contextmanager
def spin(text, numbered=False):
    """
    Only for synchronous functions.  Getting to work for async coroutines requires
    a decent amount of overhead (see yaspin.py).
    """
    from instattack.lib.logger import DisableLogger

    spinner = yaspin(text=text, color="red", numbered=numbered)
    with DisableLogger():
        spinner.start()
        try:
            yield spinner
        except Exception as e:
            spinner.error(str(e))
            spinner.done()
        finally:
            spinner.done()


def decorative_spin(text, numbered=False):
    """
    Only for synchronous functions.  Getting to work for async coroutines requires
    a decent amount of overhead (see yaspin.py).
    """
    from instattack.lib.logger import DisableLogger

    def _spin_start_and_stop(fn):
        if asyncio.iscoroutinefunction(fn):
            raise NotImplementedError('Decorator only for synchronous methods.')

        spinner = yaspin(text=text, color="red", numbered=numbered)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            with DisableLogger():
                spinner.start()
                try:
                    results = fn(*args, **kwargs)
                except Exception as e:
                    spinner.error(str(e))
                    spinner.done()
                else:
                    spinner.done()
                    return results
        return wrapper

    return _spin_start_and_stop


def break_before(fn):

    if asyncio.iscoroutinefunction(fn):

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            sys.stdout.write("\n")
            return await fn(*args, **kwargs)
        return wrapper

    else:

        @wraps(fn)
        def wrapper(*args, **kwargs):
            sys.stdout.write("\n")
            return fn(*args, **kwargs)
        return wrapper


def break_after(fn):
    if asyncio.iscoroutinefunction(fn):

        @wraps(fn)
        async def wrapper(*args, **kwargs):
            results = await fn(*args, **kwargs)
            sys.stdout.write("\n")
            return results
        return wrapper

    else:

        @wraps(fn)
        def wrapper(*args, **kwargs):
            results = fn(*args, **kwargs)
            sys.stdout.write("\n")
            return results
        return wrapper
