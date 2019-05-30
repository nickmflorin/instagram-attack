import contextlib
import decorator
import sys

from instattack.lib import logger, yaspin
from instattack import settings


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


@decorator.decorator
def break_after(func, *args, **kwargs):
    func(*args, **kwargs)
    sys.stdout.write("\n")


@decorator.decorator
def break_before(func, *args, **kwargs):
    sys.stdout.write("\n")
    func(*args, **kwargs)


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
