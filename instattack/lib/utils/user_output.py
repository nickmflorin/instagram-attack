import contextlib
import decorator
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
