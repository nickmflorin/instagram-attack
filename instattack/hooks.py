#!/usr/bin/env python3
import tortoise
import traceback
import pathlib
import sys

from termx import Cursor

from instattack.config import constants
from instattack.ext.scripts import clean
from instattack.lib import logger
from instattack.lib.utils import task_is_third_party, cancel_remaining_tasks


log = logger.get(__name__)

global _shutdown
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


async def setup(loop, spinner):

    async def setup_directories(spinner):
        with spinner.child('Setting Up Directories') as grandchild:

            grandchild.write('Removing __pycache__ Files')
            clean()

            # TODO: Validate whether files are present for all users in the
            # database.
            user_path = pathlib.Path(constants.USER_DIR)
            if not user_path.is_dir():
                grandchild.warning('User Directory Does Not Exist', fatal=False, options={
                    'label': True,
                    'color_icon': False,
                    'indent': True
                })
                grandchild.write('Creating User Directory')
                user_path.mkdir()
            else:
                grandchild.okay('User Directory Already Exists')

    async def setup_database(spinner):
        with spinner.child('Setting Up DB') as grandchild:
            grandchild.write('Closing Previous DB Connections')
            await tortoise.Tortoise.close_connections()

            grandchild.write('Configuring Database')
            await tortoise.Tortoise.init(config=constants.DB_CONFIG)

            grandchild.write('Generating Schemas')
            await tortoise.Tortoise.generate_schemas()

    async def setup_logger(spinner):
        with spinner.child('Disabling External Loggers'):
            logger.disable_external_loggers(
                'proxybroker',
                'aiosqlite',
                'db_client',
                'progressbar.utils',
                'tortoise'
            )

    await setup_logger(spinner)
    await setup_directories(spinner)
    await setup_database(spinner)


async def shutdown(loop, spinner):
    """
    The shutdown method that is tied to the Application hooks only accepts
    `app` as an argument, and we need the shutdown method tied to the exception
    hook to accept `loop`.

    Race conditions can sometimes lead to multiple shutdown attempts, which can
    raise errors due to the loop state.  We check the global _shutdown status to
    make sure we avoid this and log in case it is avoidable.
    """
    global _shutdown

    if _shutdown:
        spinner.warning('Instattack Already Shutdown...')
        return

    _shutdown = True

    async def shutdown_database(loop, child):
        with child.child('Closing DB Connections'):
            await tortoise.Tortoise.close_connections()

    async def shutdown_outstanding_tasks(loop, child):

        with child.child('Shutting Down Outstanding Tasks') as grandchild:
            futures = await cancel_remaining_tasks()
            if len(futures) != 0:
                with grandchild.child(
                        f'Cancelled {len(futures)} Leftover Tasks') as great_grandchild:
                    log_tasks = futures[:20]
                    for i, task in enumerate(log_tasks):
                        if task_is_third_party(task):
                            great_grandchild.write(f'{task._coro.__name__} (Third Party)')
                        else:
                            great_grandchild.write(f'{task._coro.__name__}')

                    if len(futures) > 20:
                        great_grandchild.write("...")
            else:
                grandchild.write(f'No Leftover Tasks to Cancel')

    await shutdown_outstanding_tasks(loop, spinner)
    await shutdown_database(loop, spinner)

    Cursor.newline()
