import asyncio
import contextlib
import decorator
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
    with DisableLogger():
        with yaspin(text=settings.Colors.GRAY(text), color="red", numbered=numbered) as spinner:
            try:
                yield spinner
            finally:
                spinner.text = settings.Colors.GREEN(text)
                spinner.ok(settings.Colors.GREEN("✔"))


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


def sync_spin_start_and_stop(text, numbered=False):

    @decorator.decorator
    def decorate(func, *args, **kwargs):
        logger.disable()

        with yaspin(text=settings.Colors.GRAY(text), color="red", numbered=numbered) as spinner:
            value = func(*args, **kwargs)
            spinner.text = settings.Colors.GREEN(text)
            spinner.ok(settings.Colors.GREEN("✔"))
            return value

        logger.enable()

    return decorate


def spin_start_and_stop(text, numbered=False):
    """
    By Default: Asynchronous

    [x] TODO:
    --------
    Allow synchronous versions as well.
    """
    @decorator.decorator
    async def decorate(coro, *args, **kwargs):
        logger.disable()
        with yaspin(text=settings.Colors.GRAY(text), color="red", numbered=numbered) as spinner:
            await coro(*args, **kwargs)
            spinner.text = settings.Colors.GREEN(text)
            spinner.ok(settings.Colors.GREEN("✔"))
        logger.enable()

    return decorate
