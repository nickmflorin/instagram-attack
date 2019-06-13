#!/usr/bin/env python3
from cement.core.exc import CaughtSignal
import sys
import warnings

from instattack.lib import logger
from instattack.core.exceptions import InstattackError

from .app import Instattack
from .hooks import system_exception_hook

log = logger.get(__name__)
warnings.simplefilter('ignore')


sys.excepthook = system_exception_hook


def instattack():
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
            app.failure(e, traceback=app.debug)

        except (CaughtSignal, KeyboardInterrupt) as e:
            app.failure('Caught Signal %s' % e, exit_code=0, tb=False)
            print('\n%s' % e)
            app.exit_code = 0

        except Exception as e:
            app.failure(e, traceback=True)


def playground():

    from .playground.main import run_playground
    run_playground()


def clean():
    from .hooks import remove_pycache
    remove_pycache()
