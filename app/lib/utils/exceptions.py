from __future__ import absolute_import

import contextlib
import logging
import traceback
import requests

from app.lib import exceptions


__all__ = ('SyncExceptionHandler', 'AysncExceptionHandler', )


class ExceptionHandlerMixin(object):

    def upstream_traceback(self, tb):
        extracted = traceback.extract_tb(tb)
        return traceback.extract_tb(tb)[len(extracted) - 1]

    def log_context(self, tb):
        """
        Providing to the log method as the value of `extra`.  We cannot get
        the actual stack trace lineno and filename to be overridden on the
        logRecord (see notes in AppLogger.makeRecord()) - so we provide custom
        values that will override if present.
        """
        upstream_tb = self.upstream_traceback(tb)
        return {
            'line_no': upstream_tb.lineno,
            'file_name': upstream_tb.filename,
        }

    def _handle_exception(self, exc_type, exc_value, tb, shutdown=False):
        # We want to do request exception handling outsie of the context.
        # Not sure why this check is necessary?
        if exc_type and exc_value:
            if issubclass(exc_type, requests.exceptions.HTTPError):
                return True
            else:
                if issubclass(exc_type, exceptions.FatalException):
                    """
                    The first line in the stack trace will refer to the first
                    block of code after the context manager is used:

                    >>> async with AysncExceptionHandler():
                    >>>   run_some_code()

                    If we go one level up in the stack trace, it is where the original
                    exception occured (unless the context manager isn't properly
                    used for nested points of failure) - but for now, this is fine.
                    """
                    self.log.critical(exc_value, extra=self.log_context(tb))

                    self.log.critical(exc_value, extra=self.log_context(tb))
                    self.log.info('Shutting Down')

                    # if shutdown:
                    #     loop = asyncio.get_running_loop()

                    #     tasks = [task for task in asyncio.Task.all_tasks() if task is not
                    #          asyncio.tasks.Task.current_task()]
                    #     list(map(lambda task: task.cancel(), tasks))
                    #     await asyncio.gather(*tasks, return_exceptions=True)

                    #     loop.stop()
                    self.log.success('From Exception Handler')
                    raise exc_value

                elif issubclass(exc_type, exceptions.InstagramAttackException):
                    self.log.error(exc_value, extra=self.log_context(tb))
                    return True
                else:
                    self.log.error(exc_value, extra=self.log_context(tb))
                    self.log.info(traceback.format_exc())
        else:
            return True


class SyncExceptionHandler(contextlib.AbstractContextManager, ExceptionHandlerMixin):

    def __init__(self, log=None):
        self.log = logging.getLogger(self.__class__.__name__)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        return self._handle_exception(exc_type, exc_value, tb)


class AysncExceptionHandler(contextlib.AbstractAsyncContextManager, ExceptionHandlerMixin):

    def __init__(self, log=None):
        self.log = logging.getLogger(self.__class__.__name__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        return self._handle_exception(exc_type, exc_value, tb, shutdown=True)
