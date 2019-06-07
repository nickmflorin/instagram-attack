#!/usr/bin/env python3
import asyncio
import warnings
import sys

from cement import App
from cement.core.exc import CaughtSignal

from instattack.config import config

from instattack.lib import logger
from instattack.lib.utils import spin_start_and_stop, start_and_stop

from .app.exceptions import InstattackError
from .controllers.base import Base, UserController, ProxyController

from .mixins import AppMixin
from .hooks import system_exception_hook, loop_exception_hook, setup, shutdown


log = logger.get(__name__)
warnings.simplefilter('ignore')


sys.excepthook = system_exception_hook


class Instattack(App, AppMixin):

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
        output_handler = config.__OUTPUT_HANDLER__

        handlers = [
            Base,
            UserController,
            ProxyController,
        ]

        # We do not specify this since we have to do it manually anyways.
        # arguments_override_config = True

    def setup(self):
        """
        Override Cement's implementation to perform setup of asynchronous
        components.

        [x] Note
        --------
        Synchronous setup/shutdown methods that are run as .setup() or .shutdown()
        from the App hooks need to call loop.run_until_complete(...) inside
        the individual methods, since the methods are sync.

            - Causes problems with pytest-asyncio, since pytest-asyncio manages
              the top level event loop in it's own fixture.

        This meant that we had to define setup/shutdown methods as async
        coroutines, and override close() and setup() to call these methods with
        the event loop.
        """
        super(Instattack, self).setup()
        self.loop.run_until_complete(setup(self.loop))

    def close(self, code=None):
        """
        Override Cement's implementation to perform shutdown of asynchronous
        components.

        [x] Note
        --------
        Synchronous setup/shutdown methods that are run as .setup() or .shutdown()
        from the App hooks need to call loop.run_until_complete(...) inside
        the individual methods, since the methods are sync.

            - Causes problems with pytest-asyncio, since pytest-asyncio manages
              the top level event loop in it's own fixture.

        This meant that we had to define setup/shutdown methods as async
        coroutines, and override close() and setup() to call these methods with
        the event loop.
        """
        self.loop.run_until_complete(shutdown(self.loop))
        self.loop.close()
        super(Instattack, self).close(code=code)

    def validate_config(self):
        """
        Validates the configuration against a Cerberus schema.  If the configuration
        is valid, it will be set to the global config object in its dictionary
        form.
        """
        with start_and_stop('Validating Config') as spinner:
            super(Instattack, self).validate_config()
            data = self.config.get_dict()

            spinner.warning('Not Currently Validating Schema')
            # config.validate(data, set=False)
            config.set(data)

            # Since we are not using the Cement logger, we have to set this
            # manually.
            logger.configure(config)

    @spin_start_and_stop('Attaching Exit Signals to Loop')
    def attach_signals(self):
        """
        [x] TODO:
        -------
        This is currently not working because the signals need to be attached
        at the very top level in main().
        """
        # Requires Sync Version of Shutdown - Signals Not Working Now Anyways
        def _shutdown(loop, s):
            self.loop.run_until_complete(shutdown(loop))

        for s in config.__SIGNALS__:
            self.loop.add_signal_handler(s, _shutdown)

    def __enter__(self):
        """
        Override Cement's implementation to set the event loop and attach it
        to the app instance.
        """
        self.loop = asyncio.get_event_loop()
        self.attach_signals()
        self.loop.set_exception_handler(loop_exception_hook)
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        # Only Close App if No Unhandled Exceptions
        if exc_type is None:
            self.close()


def main():
    """
    [x] TODO:
    --------
    (1) Adding SIGNAL Handlers to Loop - Sync Methods of Controllers Make Difficult
    (2) Curses Logging/Initialization
    (3) Loop Exception Handler at Top Level
    (4) Reimplementation: Validation of Config Schema
    """
    with Instattack() as app:
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
