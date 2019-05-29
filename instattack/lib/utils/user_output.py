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
