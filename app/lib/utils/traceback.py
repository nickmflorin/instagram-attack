from __future__ import absolute_import

import traceback


__all__ = ('get_stack', 'get_traceback_info', 'log_tb_context', )


def get_stack(tb=None):
    if tb:
        stack = traceback.extract_tb(tb)
    else:
        stack = traceback.extract_stack()
    stack = [st for st in stack if not st.filename.startswith('/Library/Frameworks/')]
    return stack


def get_traceback_info(tb=None, stack=None, backstep=1):
    if not stack:
        backstep += 1
        stack = get_stack(tb=tb)

    frame = stack[-(backstep)]

    return {
        'lineno': frame.lineno,
        'filename': frame.filename,
    }


def log_tb_context(tb=None, stack=None, backstep=1):
    """
    Providing to the log method as the value of `extra`.  We cannot get
    the actual stack trace lineno and filename to be overridden on the
    logRecord (see notes in AppLogger.makeRecord()) - so we provide custom
    values that will override if present.
    """
    backstep += 1
    return get_traceback_info(tb=tb, stack=stack, backstep=backstep)
