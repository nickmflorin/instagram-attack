#!/usr/bin/env python3
import pathlib
import tortoise
import traceback
import sys

from instattack.config import constants

from instattack.lib import logger
from instattack.lib.utils import task_is_third_party, cancel_remaining_tasks, spin


log = logger.get(__name__)

_shutdown = False


def system_exception_hook(exc_type, exc_value, exc_traceback):
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


def remove_pycache():
    [p.unlink() for p in pathlib.Path(constants.APP_DIR).rglob('*.py[co]')]
    [p.rmdir() for p in pathlib.Path(constants.APP_DIR).rglob('__pycache__')]


def loop_exception_hook(self, loop, context):
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
    loop.run_until_complete(shutdown(loop))


async def setup(loop):

    async def setup_directories(spinner):
        spinner.write('Setting Up Directories')

        with spinner.block():

            spinner.write('Removing __pycache__ Files')
            remove_pycache()

            if not constants.USER_PATH.exists():
                spinner.write('User Directory Does Not Exist', failure=True)
                spinner.write('Creating User Directory')
                constants.USER_PATH.mkdir()
            else:
                spinner.write('User Directory Already Exists', success=True)

        pass

    async def setup_database(spinner):
        spinner.write('Setting Up DB')

        with spinner.block():
            spinner.write('Closing Previous DB Connections')
            await tortoise.Tortoise.close_connections()

            spinner.write('Configuring Database')
            await tortoise.Tortoise.init(config=constants.DB_CONFIG)

            spinner.write('Generating Schemas')
            await tortoise.Tortoise.generate_schemas()

    async def setup_logger(spinner):
        spinner.write('Disabling External Loggers')
        logger.disable_external_loggers(
            'proxybroker',
            'aiosqlite',
            'db_client',
            'progressbar.utils',
            'tortoise'
        )

    with spin('Setting Up') as spinner:
        await setup_logger(spinner)
        await setup_directories(spinner)
        await setup_database(spinner)


async def shutdown(loop):
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

    async def shutdown_database(loop, spinner):
        spinner.write('Closing DB Connections')
        await tortoise.Tortoise.close_connections()

    async def shutdown_outstanding_tasks(loop, spinner):
        spinner.write('Shutting Down Outstanding Tasks')

        futures = await cancel_remaining_tasks()
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

    with spin('Shutting Down') as spinner:
        await shutdown_outstanding_tasks(loop, spinner)
        await shutdown_database(loop, spinner)
