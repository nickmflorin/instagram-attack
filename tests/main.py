#!/usr/bin/env python3
import asyncio
import warnings

from cement import App, TestApp

from instattack.config import config, constants
from instattack.hooks import setup, shutdown
from instattack.lib.utils import start_and_stop


warnings.simplefilter('ignore')


class InstattackTest(TestApp, App):

    class Meta:
        label = constants.APP_NAME

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

        # handlers = [Base]

    async def setup(self):
        """
        Override Cement's implementation to perform shutdown of asynchronous
        components.  Unlike the case of non-test App, we can make the setup
        and close methods async, and call them from within the context of the
        async generator:

        >>> async with InstattackTest() as app:
        >>>    await some_function_in_test()

        This is because we don't have to worry about running the application
        in the async context manager (which would break).  For example, this
        would fail:

        >>> async with Instattack() as app:
        >>> try:
        >>>     app.run()

        Fixing that requires a lot of overhead.  Instead, we just make our
        test version, InstattackTest, operate as an async context manager,
        since it does not need to call app.run().
        """
        super(InstattackTest, self).setup()
        await setup(self.loop)

    async def close(self, code=None):
        """
        Override Cement's implementation to perform shutdown of asynchronous
        components.  See discusion in .setup() method about reasoning for
        async implementation of .close() and .setup() methods.

        [x] NOTE:
        --------
        pytest-asyncio handles the context of the event loop, so we cannot close
        the loop since it is down inside the context of the test case.

        pytest will also have probems if we call super().close(), since that
        calls sys.exit() which we do not want.
        """
        await shutdown(self.loop)

    def validate_config(self):
        """
        Validates the configuration against a Cerberus schema.  If the configuration
        is valid, it will be set to the global config object in its dictionary
        form.

        [x] TODO:
        --------
        Use test specific configuration.
        """
        with start_and_stop('Validating Config') as spinner:
            super(InstattackTest, self).validate_config()
            data = self.config.get_dict()

            spinner.warning('Not Currently Validating Schema')
            # config.validate(data, set=False)
            config.set(data)

    async def __aenter__(self):
        """
        Override Cement's implementation to set the event loop and attach it
        to the app instance.
        """
        self.loop = asyncio.get_event_loop()
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        # Only Close App if No Unhandled Exceptions
        if exc_type is None:
            await self.close()
