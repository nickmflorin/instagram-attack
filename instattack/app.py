#!/usr/bin/env python3
import asyncio
import sys

from blinker import signal
from cement import App
import threading

from instattack import settings

from termx.config import config
from termx.spinner import Spinner
from termx.ext.utils import break_before

from instattack.lib import logger
from instattack.lib.diagnostics import run_diagnostics

from .controllers.base import Base, UserController, ProxyController
from .hooks import loop_exception_hook, setup, shutdown


diagnostics = signal('diagnostics')
log = logger.get(__name__)


class Instattack(App):

    class Meta:
        label = 'instattack'

        # Default configuration dictionary.
        config_section = settings.CONFIG_SECTION
        config_dirs = settings.CONFIG_DIRS
        config_files = settings.CONFIG_FILES
        config_handler = settings.CONFIG_HANDLER
        config_file_suffix = settings.CONFIG_FILE_SUFFIX

        config_defaults = {
            'connection': {},
            'passwords': {},
            'attempts': {},
            'pool': {},
            'broker': {},
            'proxies': {}
        }

        exit_on_close = settings.EXIT_ON_CLOSE  # Call sys.exit() on Close
        extensions = settings.EXTENSIONS
        output_handler = settings.OUTPUT_HANDLER

        handlers = [
            Base,
            UserController,
            ProxyController,
        ]

        # We do not specify this since we have to do it manually anyways.
        # arguments_override_config = True

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

        [x] TODO:
        --------
        Start validating the config schema again.
        >>> config.validate(data, set=False)

        [x] NOTE
        -------
        Since we are not using the Cement logger, we have to set the level
        manually.  The base controller also has an argument for logging level,
        which will override the level from config if specified.
        """
        # with self.spinner.reenter('Validating Config') as grandchild:
        super(Instattack, self).validate_config()
        data = self.config.get_dict()
        config(data)

        # grandchild.warning('Not Currently Validating Schema', fatal=False, options={
        #     'label': True,
        # })

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
            for s in settings.SIGNALS:
                self.loop.add_signal_handler(s, _shutdown)

            grandchild.write('Attaching Exception Handler')
            self.loop.set_exception_handler(loop_exception_hook)
            grandchild.warning('Exception Handler Not Attached to Loop', fatal=False, options={
                'label': True,
            })

    def run_diagnostics(self):
        thread = threading.Thread(target=run_diagnostics)
        thread.start()

        import time
        time.sleep(2)
        diagnostics.send({'dialog': 'logging', 'data': 'Message Bitch'})
        thread.join()

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
