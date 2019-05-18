import contextlib
import progressbar
import logging


__all__ = (
    'progressbar_wrap',
    'disable_external_loggers',
)


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


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
