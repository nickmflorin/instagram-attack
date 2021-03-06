#!/usr/bin/env python3
from cement.core.exc import CaughtSignal
import sys
import warnings

warnings.simplefilter('ignore')


def instattack():
    """
    [x] TODO:
    --------
    (1) Adding SIGNAL Handlers to Loop - Sync Methods of Controllers Make Difficult
    (2) Curses Logging/Initialization
    (3) Loop Exception Handler at Top Level
    (4) Reimplementation: Validation of Config Schema
    """
    from .core.exceptions import InstattackError
    from .app import Instattack

    from .hooks import system_exception_hook
    sys.excepthook = system_exception_hook

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


def run_playground():
    """
    This module is only for developer environments.

    Creating a sub-module where we can store test code, duplicate and modified versions
    of existing code and explore programming possibilities is a crucial part of
    this project.

    It is in this module where we play around with certain packages, code and
    ideas, not being in the Cement app framework but still having access to the
    components that make up the instattack app.

    [x] TODO:
    --------
    Remove from production distribution/package.
    """
    from .playground import playground
    playground()


def clean():
    from termx.library import remove_pybyte_data
    from .ext import get_app_root

    root = get_app_root()
    print('Cleaning %s' % root)
    remove_pybyte_data(root)


def cleanroot():
    from termx.library import remove_pybyte_data
    from .ext import get_root

    root = get_root()
    print('Cleaning %s' % root)
    remove_pybyte_data(root)
