import asyncio
import contextlib
from platform import python_version
import signal
import sys
import tortoise

from plumbum import cli

from lib import validate_log_level, cancel_remaining_tasks, log_handling

from instattack.db import database_init
from instattack.handlers.control import Loggable


class BaseApplication(cli.Application, Loggable):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.

    TODO
    ----

    .cleanup()
    Method performed in cli.Application after all components of main() have
    completed.

    May want to catch other signals too - these are not currently being
    used, but could probably be expanded upon.
    """
    SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

    level = cli.SwitchAttr("--level", validate_log_level, default='INFO')

    @contextlib.contextmanager
    def loop_session(self):
        """
        TODO:
        ----

        Look into situations in which the following:
        >>> loop.set_exception_handler(self.handle_exception)
        is used to handle exceptions, instead of the exception catches, (i.e.)

        >>> try:
        >>>     loop.run_until_complete(self.method(loop))
        >>> except Exception as e:
        >>>     # When exception is raised here, vs. passed to the exception handler.
        >>>     self.log.error(e)
        >>>     await loop.run_until_complete(self.shutdown(loop))

        It has something to do with asyncio.gather() and the way that exceptions
        are suppressed.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.get_running_loop()

        try:
            loop.run_until_complete(database_init())
            loop.set_exception_handler(self.handle_exception)
            yield loop
        finally:
            # We have to do this just in case errors are caught by both the
            # handler and the catch block, until we figure out how to handle that,
            # since we cannot shut down the loop twice.
            # >>> RuntimeError: This event loop is already running
            try:
                self.log.debug('Shutting Down in loop_session')
                self.shutdown(loop)
                loop.close()
            except RuntimeError:
                self.log.error('Loop was already shutdown... this should not be happening.')
                pass

    def handle_exception(self, loop, context):
        """
        We are having trouble using log.exception() with exc_info=True and seeing
        the stack trace, so we have a custom log.traceback() method for now.

        >>> self.log.exception(exc, exc_info=True, extra=extra)

        Not sure if we will keep it or not, since it might add some extra
        customization availabilities, but it works right now.
        """
        extra = {}
        if 'message' in context:
            extra['other'] = context['message']

        exc = context['exception']
        self.log.traceback(exc)

        try:
            self.log.debug('Shutting Down in handle_exception')
            loop.run_until_complete(self.shutdown(loop))
            loop.close()
        except RuntimeError:
            self.log.error('Loop was already shutdown... this should not be happening.')
            pass

    def shutdown(self, loop, signal=None):

        if signal:
            self.log.error(f'Received exit signal {signal.name}...')

        self.log.warning('[!] Shutting Down...')

        self.log.warning('[1] Cancelling Tasks...')
        loop.run_until_complete(cancel_remaining_tasks())

        self.log.warning('[2] Shutting Down DB')
        loop.run_until_complete(tortoise.Tortoise.close_connections())

        loop.stop()
        self.log.notice('[!] Done')


class Instattack(BaseApplication):

    @log_handling('self')
    def main(self, *args):
        self.validate(*args)

    def validate(self, *args):
        if int(python_version()[0]) < 3:
            self.log.error('Please use Python 3')
            sys.exit()
        if args:
            self.log.error("Unknown command %r" % (args[0]))
            sys.exit()
        # The nested command will be`None if no sub-command follows
        if not self.nested_command:
            self.log.error("No command given")
            sys.exit()
