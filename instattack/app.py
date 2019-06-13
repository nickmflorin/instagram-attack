#!/usr/bin/env python3
import asyncio
import sys

from cement import App
from cement.core.arg import ArgumentHandler

from termx import Spinner

from instattack.config import config, constants

from instattack.lib import logger
from instattack.lib.utils import break_before
from instattack.lib.diagnostics import run_diagnostics

from .controllers.base import Base, UserController, ProxyController
from .hooks import loop_exception_hook, setup, shutdown


spinner = Spinner(color="red")
log = logger.get(__name__)


class AppMixin(object):

    @break_before
    def success(self, text):
        sys.stdout.write("%s\n" % constants.LoggingLevels.SUCCESS(text))

    @break_before
    def failure(self, e, exit_code=1, traceback=True):
        sys.stdout.write("%s\n" % constants.LoggingLevels.ERROR(str(e)))

        self.exit_code = exit_code

        # We might not want to do this for all errors - argument errors or things
        # that are more expected we don't need to provide the traceback.
        if self.debug is True or traceback:
            log.traceback(e.__class__, e, e.__traceback__)


from argparse import ArgumentParser
from cement import Controller


class AsyncArgumentHandler(ArgumentParser, ArgumentHandler):

    class Meta:
        label = 'async_argument_handler'
        ignore_unknown_arguments = False
        interface = 'argument'

    def parse(self, arg_list):
        """
        Parse a list of arguments, and return them as an object.  Meaning an
        argument name of 'foo' will be stored as parsed_args.foo.
        Args:
            arg_list (list): A list of arguments (generally sys.argv) to be
                parsed.
        Returns:
            object: Instance object whose members are the arguments parsed.
        """

        if self._meta.ignore_unknown_arguments is True:
            args, unknown = self.parse_known_args(arg_list)
            self.parsed_args = args
            self.unknown_args = unknown
        else:
            args = self.parse_args(arg_list)
            self.parsed_args = args
        return self.parsed_args

    def add_argument(self, *args, **kw):
        """
        Add an argument to the parser.  Arguments and keyword arguments are
        passed directly to ``ArgumentParser.add_argument()``.
        See the :py:class:`argparse.ArgumentParser` documentation for help.
        """
        super(AsyncArgumentHandler, self).add_argument(*args, **kw)



class ArgparseController(Controller):

    class Meta:
        label = 'argparse'

    def _dispatch(self):
        raise Exception()
        super(AsyncArgumentHandler, self)._dispatch()



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
        argument_handler = 'async_argument_handler'

        handlers = [
            Base,
            UserController,
            ProxyController,
            AsyncArgumentHandler,
            ArgparseController,
        ]

        # We do not specify this since we have to do it manually anyways.
        # arguments_override_config = True

    def _setup_controllers(self):

        if self.handler.registered('controller', 'base'):
            self.controller = self._resolve_handler('controller', 'base')

        else:
            class DefaultBaseController(ArgparseController):
                class Meta:
                    label = 'base'

                def _default(self):
                    # don't enforce anything cause developer might not be
                    # using controllers... if they are, they should define
                    # a base controller.
                    pass

            self.handler.register(DefaultBaseController)
            self.controller = self._resolve_handler('controller', 'base')

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
        with spinner.group('Validating Config') as sp:
            super(Instattack, self).validate_config()
            data = self.config.get_dict()

            sp.warning('Not Currently Validating Schema')
            # config.validate(data, set=False)
            config.set(data)

            # Since we are not using the Cement logger, we have to set this
            # manually.
            logger.configure(config)

    def setup_loop(self):
        """
        [x] TODO:
        -------
        This is currently not working because the signals need to be attached
        at the very top level in main().
        """
        # Requires Sync Version of Shutdown - Signals Not Working Now Anyways
        def _shutdown(loop, s):
            self.loop.run_until_complete(shutdown(loop))

        with spinner.group('Configuring Event Loop') as sp:
            sp.write('Attaching Exit Signals')
            sp.warning('Exit Signals Currently Not Working')
            for s in config.__SIGNALS__:
                self.loop.add_signal_handler(s, _shutdown)

            sp.write('Attaching Exception Handler')
            self.loop.set_exception_handler(loop_exception_hook)
            sp.warning('Exception Handler Currently Not Working')

    def run_diagnostics(self):
        self.loop.create_task(run_diagnostics())

    def __enter__(self):
        """
        Override Cement's implementation to set the event loop and attach it
        to the app instance.
        """
        self.loop = asyncio.get_event_loop()
        self.setup_loop()
        self.setup()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        # Only Close App if No Unhandled Exceptions
        if exc_type is None:
            self.close()
