import contextlib
import decorator
import sys
from yaspin import yaspin

from instattack import settings


@contextlib.contextmanager
def start_and_stop(text):
    with yaspin(text=settings.Colors.GRAY(text), color="red") as spinner:
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


def spin_start_and_stop(text):
    """
    By Default: Asynchronous

    [x] TODO:
    --------
    Allow synchronous versions as well.
    """
    @decorator.decorator
    async def decorate(coro, *args, **kwargs):
        with yaspin(text=settings.Colors.GRAY(text), color="red") as spinner:
            await coro(*args, **kwargs)
            spinner.text = settings.Colors.GREEN(text)
            spinner.ok(settings.Colors.GREEN("✔"))

    return decorate
