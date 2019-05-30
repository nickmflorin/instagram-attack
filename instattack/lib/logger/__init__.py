import logging

from instattack.app import settings

from .logger import *  # noqa


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


def get_async(name, subname=None):

    # There is probably a better way to do this, but I have been unable to shield
    # all of the files in the src directory from being imported before the
    # LEVEL is set in os.environ in __main__.py.
    # if 'LEVEL' not in os.environ:
    #     print('WARNING: LEVEL must be in ENV variables before %s '
    #         'logger is imported.' % name)

    if settings.SIMPLE_LOGGER:
        return SimpleAsyncLogger(name)

    return AsyncLogger(name, subname=subname)


def get_sync(name, subname=None):

    # There is probably a better way to do this, but I have been unable to shield
    # all of the files in the src directory from being imported before the
    # LEVEL is set in os.environ in __main__.py.
    # if 'LEVEL' in os.environ:
    #     print('WARNING: LEVEL must be in ENV variables before %s '
    #         'logger is imported.' % name)

    if settings.SIMPLE_LOGGER:
        return SimpleSyncLogger(name)

    return SyncLogger(name, subname=subname)
