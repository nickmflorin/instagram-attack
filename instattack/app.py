#!/usr/bin/env python3
import asyncio
import sys

from cement import App

from termx import Formats, Spinner
from termx.ext.utils import break_before

from instattack.config import config

from instattack.lib import logger
from instattack.lib.diagnostics import run_diagnostics

from .controllers.base import Base, UserController, ProxyController
from .hooks import loop_exception_hook, setup, shutdown


log = logger.get(__name__)


class AppMixin(object):

    @break_before
    def success(self, text):
        sys.stdout.write("%s\n" % Formats.SUCCESS(text))

    @break_before
    def failure(self, e, exit_code=1, traceback=True):
        sys.stdout.write("%s\n" % Formats.ERROR(str(e)))

        self.exit_code = exit_code

        # We might not want to do this for all errors - argument errors or things
        # that are more expected we don't need to provide the traceback.
        if self.debug is True or traceback:
            log.traceback(e.__class__, e, e.__traceback__)


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

    def setup(self, group):
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
        self.loop.run_until_complete(setup(self.loop, group))

    def close(self, group, code=None):
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
        self.loop.run_until_complete(shutdown(self.loop, group))
        self.loop.close()
        super(Instattack, self).close(code=code)

    def validate_config(self):
        """
        Validates the configuration against a Cerberus schema.  If the configuration
        is valid, it will be set to the global config object in its dictionary
        form.
        """
        with self.spinner.reenter('Validating Config') as grandchild:
            super(Instattack, self).validate_config()
            data = self.config.get_dict()

            grandchild.warning('Not Currently Validating Schema', fatal=False, options={
                'label': True,
            })

            # config.validate(data, set=False)
            config.set(data)

            # Since we are not using the Cement logger, we have to set this
            # manually.
            logger.configure(config)

    def setup_loop(self, child):
        """
        [x] TODO:
        -------
        This is currently not working because the signals need to be attached
        at the very top level in main().
        """
        # Requires Sync Version of Shutdown - Signals Not Working Now Anyways
        def _shutdown(loop, s):
            self.loop.run_until_complete(shutdown(loop, self.spinner))

        with child.child('Configuring Event Loop') as grandchild:
            grandchild.write('Attaching Exit Signals')
            grandchild.warning('Exit Signals Not Attached to Loop', fatal=False, options={
                'label': True,
            })
            for s in config.__SIGNALS__:
                self.loop.add_signal_handler(s, _shutdown)

            grandchild.write('Attaching Exception Handler')
            self.loop.set_exception_handler(loop_exception_hook)
            grandchild.warning('Exception Handler Not Attached to Loop', fatal=False, options={
                'label': True,
            })

    def run_diagnostics(self):
        self.loop.run_until_complete(run_diagnostics())
        # self.loop.run_forever()

    def __enter__(self):
        """
        Override Cement's implementation to set the event loop and attach it
        to the app instance.
        """
        self.loop = asyncio.get_event_loop()
        self.spinner = Spinner(color="CornflowerBlue")

        with self.spinner.child('Setting Up Application...') as child:
            self.setup_loop(child)
            self.setup(child)
            return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        # Only Close App if No Unhandled Exceptions
        with self.spinner.child('Shutting Down') as child:
            if exc_type is None:
                self.close(child)
