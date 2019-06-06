#!/usr/bin/env python3
import asyncio
import pathlib
import tortoise
import traceback
import warnings
import sys

from cement import App, TestApp
from cement.core.exc import CaughtSignal

from instattack.config import config, settings

from instattack.lib import logger
from instattack.lib.utils import (
    spin_start_and_stop, task_is_third_party,
    cancel_remaining_tasks, start_and_stop, break_before)

from .app.exceptions import InstattackError
from .controllers.base import Base, UserController, ProxyController

from .mixins import AppMixin


log = logger.get(__name__)


def exception_hook(exc_type, exc_value, exc_traceback):
    """
    You can log all uncaught exceptions on the main thread by assigning a handler
    to sys.excepthook.
    """
    try:
        log.traceback(exc_type, exc_value, exc_traceback)
    except BlockingIOError:
        # This will clog the output a big but at least we will have the end
        # of the stack trace to diagnose errors.
        tb = traceback.format_exception(exc_type, exc_value, exc_traceback)
        lines = tb[-50:]
        sys.stdout.write("\n".join(lines))
        pass


sys.excepthook = exception_hook

warnings.simplefilter('ignore')

_shutdown = False


def handle_exception(loop, context):
    """
    We are having trouble using log.exception() with exc_info=True and seeing
    the stack trace, so we have a custom log.traceback() method for now.

    >>> self.log.exception(exc, exc_info=True, extra=extra)

    Not sure if we will keep it or not, since it might add some extra
    customization availabilities, but it works right now.
    """
    log = logger.get('handle_exception', sync=True)
    log.debug('Handling Exception')

    # The only benefit including the frame has is that the filename
    # will not be in the logger, it will be in the last place before the
    # logger and this statement.
    try:
        log.traceback(
            context['exception'].__class__,
            context['exception'],
            context['exception'].__traceback__,
        )
    except BlockingIOError:
        log.warning('Could Not Output Traceback due to Blocking IO')

    log.debug('Shutting Down in Exception Handler')
    shutdown(loop)


@break_before
def setup(app):

    loop = asyncio.get_event_loop()

    def setup_directories(spinner):
        spinner.write('Setting Up Directories')

        with spinner.block():

            spinner.write('Removing __pycache__ Files')
            [p.unlink() for p in pathlib.Path(settings.APP_DIR).rglob('*.py[co]')]
            [p.rmdir() for p in pathlib.Path(settings.APP_DIR).rglob('__pycache__')]

            if not settings.USER_PATH.exists():
                spinner.write('User Directory Does Not Exist', failure=True)
                spinner.write('Creating User Directory')
                settings.USER_PATH.mkdir()
            else:
                spinner.write('User Directory Already Exists', success=True)

        pass

    def setup_database(spinner):
        spinner.write('Setting Up DB')

        with spinner.block():
            spinner.write('Closing Previous DB Connections')
            loop.run_until_complete(tortoise.Tortoise.close_connections())

            spinner.write('Configuring Database')
            loop.run_until_complete(tortoise.Tortoise.init(config=settings.DB_CONFIG))

            spinner.write('Generating Schemas')
            loop.run_until_complete(tortoise.Tortoise.generate_schemas())

    def setup_logger(spinner):
        spinner.write('Disabling External Loggers')
        logger.disable_external_loggers(
            'proxybroker',
            'aiosqlite',
            'db_client',
            'progressbar.utils',
            'tortoise'
        )

    with start_and_stop('Preparing') as spinner:
        setup_logger(spinner)
        setup_directories(spinner)
        setup_database(spinner)


@break_before
def shutdown(*args, **kwargs):
    """
    The shutdown method that is tied to the Application hooks only accepts
    `app` as an argument, and we need the shutdown method tied to the exception
    hook to accept `loop`.

    Race conditions can sometimes lead to multiple shutdown attempts, which can
    raise errors due to the loop state.  We check the global _shutdown status to
    make sure we avoid this and log in case it is avoidable.
    """
    log = logger.get(__name__, subname='shutdown')

    global _shutdown
    if _shutdown:
        log.warning('Instattack Already Shutdown...')
        return

    _shutdown = True

    if isinstance(args[0], App):
        loop = asyncio.get_event_loop()
    else:
        loop = args[0]

    def shutdown_database(spinner):
        spinner.write('Closing DB Connections')
        loop.run_until_complete(tortoise.Tortoise.close_connections())

    def shutdown_outstanding_tasks(spinner):
        spinner.write('Shutting Down Outstanding Tasks')

        futures = loop.run_until_complete(cancel_remaining_tasks())
        if len(futures) != 0:

            with spinner.block():
                spinner.write(f'Cancelled {len(futures)} Leftover Tasks')
                spinner.number()

                with spinner.block():
                    log_tasks = futures[:20]
                    for i, task in enumerate(log_tasks):
                        if task_is_third_party(task):
                            spinner.write(f'{task._coro.__name__} (Third Party)')
                        else:
                            spinner.write(f'{task._coro.__name__}')

                    if len(futures) > 20:
                        spinner.write("...")
        else:
            spinner.write(f'No Leftover Tasks to Cancel')

    with start_and_stop('Shutting Down') as spinner:
        shutdown_outstanding_tasks(spinner)
        shutdown_database(spinner)

        spinner.write('Closing Loop')
        loop.close()


@spin_start_and_stop('Setting Up Loop')
def setup_loop(app):

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    for s in config.__SIGNALS__:
        loop.add_signal_handler(s, shutdown)


class Instattack(App, AppMixin):
    """
    [x] TODO:
    --------
    Figure out if there is a seamless/easy way to tie in the cement log handler
    with our logging system.
    """
    class Meta:
        label = 'instattack'

        # Default configuration dictionary.
        config_section = config.__CONFIG_SECTION__
        config_dirs = config.__CONFIG_DIRS__
        config_files = config.__CONFIG_FILES__
        config_handler = config.__CONFIG_HANDLER__
        config_file_suffix = config.__CONFIG_FILE_SUFFIX__

        config_defaults = {
            'connection': {},
            'passwords': {},
            'attempts': {},
            'pool': {},
            'broker': {},
            'proxies': {}
        }

        exit_on_close = config.__EXIT_ON_CLOSE__  # Call sys.exit() on Close
        extensions = config.__EXTENSIONS__

        log_handler = config.__LOG_HANDLER__
        output_handler = config.__OUTPUT_HANDLER__

        arguments_override_config = True

        hooks = [
            ('pre_setup', setup),
            ('post_run', shutdown),
        ]

        handlers = [
            Base,
            UserController,
            ProxyController,
        ]

    def run(self):
        self.loop = asyncio.get_event_loop()
        super(Instattack, self).run()

    @spin_start_and_stop('Validating Config')
    def validate_config(self):
        """
        Validates the configuration against a Cerberus schema.  If the configuration
        is valid, it will be set to the global config object in its dictionary
        form.
        """
        super(Instattack, self).validate_config()
        data = self.config.get_dict()

        print('Warning: Not Validating Schema')

        # We will start validating the schema again once it settles down and
        # we stop adding attributes.
        # config.validate(data, set=False)
        config.set(data)

        # Since we are not using the Cement logger, we have to set this
        # manually.
        logger.setLevel(config['instattack']['log.logging']['level'])


class InstattackTest(TestApp, Instattack):

    class Meta:
        label = settings.APP_NAME

        # Default configuration dictionary.
        config_section = config.__CONFIG_SECTION__
        config_dirs = config.__CONFIG_DIRS__
        config_files = config.__CONFIG_FILES__
        config_handler = config.__CONFIG_HANDLER__
        config_file_suffix = config.__CONFIG_FILE_SUFFIX__

        config_defaults = {
            'connection': {},
            'passwords': {},
            'attempts': {},
            'pool': {},
            'broker': {},
            'proxies': {}
        }

        exit_on_close = config.__EXIT_ON_CLOSE__  # Call sys.exit() on Close
        extensions = config.__EXTENSIONS__

        hooks = [
            ('pre_setup', setup),
        ]

        # Register Handlers
        handlers = [
            Base,
        ]


def main():
    """
    Default Cement signals are SIGINT and SIGTERM, exit 0 (non-error)

    [x] TODO:
    --------
    Maybe remove signals from our loop handler to avoid unnecessary
    signal attachment - also might want to perform save tasks here, where
    signal casues failure.
    """
    with Instattack() as app:
        setup_loop(app)  # Wait for App Config to be Set
        try:
            app.run()

        except AssertionError as e:
            if len(e.args) != 0:
                app.failure('AssertionError > %s' % e.args)
            else:
                app.failure('Assertion Error')

        except InstattackError as e:
            app.failure(str(e))
            if app.debug:
                log.traceback(e.__class__, e, e.__traceback__)

        except (CaughtSignal, KeyboardInterrupt) as e:
            app.failure('Caught Signal %s' % e, exit_code=0, tb=False)
            print('\n%s' % e)
            app.exit_code = 0


if __name__ == '__main__':
    main()
