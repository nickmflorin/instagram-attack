import contextlib
import progressbar
import logging

from .handlers import BARE_HANDLER, SIMPLE_HANDLER, BASE_HANDLER
from .handlers import ExternalHandler


__all__ = (
    'progressbar_wrap',
    'disable_external_loggers',
    'apply_external_loggers',
)


def add_base_handlers(logger):
    for handler in [BARE_HANDLER, SIMPLE_HANDLER, BASE_HANDLER]:
        logger.addHandler(handler)


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


def apply_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        for handler in external_logger.handlers:
            external_logger.removeHandler(handler)

        external_logger.addHandler(ExternalHandler())
        external_logger.propagate = False


@contextlib.contextmanager
def progressbar_wrap():

    def _init_progressbar():
        progressbar.streams.wrap_stderr()
        progressbar.streams.wrap_stdout()

    def _deinit_progressbar():
        progressbar.streams.unwrap_stdout()
        progressbar.streams.unwrap_stderr()

    try:
        _init_progressbar()
        yield
    finally:
        _deinit_progressbar()
