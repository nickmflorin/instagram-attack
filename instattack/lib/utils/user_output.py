import contextlib
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
    def decorator(func):
        async def wrapped(*args, **kwargs):
            with yaspin(text=settings.Colors.GRAY(text), color="red") as spinner:
                await func(*args, **kwargs)
                spinner.text = settings.Colors.GREEN(text)
                spinner.ok(settings.Colors.GREEN("✔"))
        return wrapped
    return decorator
