import asyncio
import contextlib
from functools import wraps
import sys

from termx import Spinner


spinner = Spinner(color="red")


@contextlib.contextmanager
def spin(text, numbered=False):
    """
    Only for synchronous functions.  Getting to work for async coroutines requires
    a decent amount of overhead (see yaspin.py).
    """
    from instattack.lib.logger import DisableLogger

    with DisableLogger():
        with spinner.group(text):
            try:
                yield spinner
            except Exception as e:
                spinner.error(str(e))
            finally:
                return


def decorative_spin(text, numbered=False):
    """
    Only for synchronous functions.  Getting to work for async coroutines requires
    a decent amount of overhead (see yaspin.py).
    """
    from instattack.lib.logger import DisableLogger

    def _spin_start_and_stop(fn):
        if asyncio.iscoroutinefunction(fn):
            raise NotImplementedError('Decorator only for synchronous methods.')

        spinner = Spinner(text, color="red")

        @wraps(fn)
        def wrapper(*args, **kwargs):
            with DisableLogger():
                with spinner.group(text):
                    try:
                        results = fn(*args, **kwargs)
                    except Exception as e:
                        spinner.error(str(e))
                    else:
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
