import asyncio
import contextlib
from functools import wraps
import sys

from instattack.lib import logger, yaspin
from instattack.config import settings


class DisableLogger():

    def __enter__(self):
        logger.disable()

    def __exit__(self, a, b, c):
        logger.enable()


@contextlib.contextmanager
def start_and_stop(text, numbered=False):
    """
    Only for synchronous functions.  Getting to work for async coroutines requires
    a decent amount of overhead (see yaspin.py).
    """
    logger.disable()
    spinner = yaspin(text=settings.Colors.GRAY(text), color="red", numbered=numbered)
    try:
        spinner.start()
        yield spinner
    finally:
        spinner.text = settings.Colors.GREEN(text)
        spinner.ok(settings.Colors.GREEN("✔"))

        spinner.stop()
        logger.enable()


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


def spin_start_and_stop(text, numbered=False):
    """
    Only for synchronous functions.  Getting to work for async coroutines requires
    a decent amount of overhead (see yaspin.py).
    """
    def _spin_start_and_stop(fn):

        if asyncio.iscoroutinefunction(fn):
            raise NotImplementedError('Decorator only for synchronous methods.')

        spinner = yaspin(
            text=settings.Colors.GRAY(text),
            color="red",
            numbered=numbered
        )

        @wraps(fn)
        def wrapper(*args, **kwargs):
            logger.disable()
            spinner.start()

            results = fn(*args, **kwargs)

            spinner.text = settings.Colors.GREEN(text)
            spinner.ok(settings.Colors.GREEN("✔"))

            spinner.stop()
            logger.enable()

            return results
        return wrapper

    return _spin_start_and_stop
