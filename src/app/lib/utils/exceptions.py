from __future__ import absolute_import

import aiohttp


def handle_global_exception(exc, exc_info=None, callback=None):

    ex_type, ex, tb = exc_info
    log = tb.tb_frame.f_globals.get('log')
    if not log:
        log = tb.tb_frame.f_locals.get('log')

    # Array of lines for the stack trace - might be useful later.
    # trace = traceback.format_exception(ex_type, ex, tb, limit=3)

    if not callback:
        log.exception(exc, extra={
            'lineno': tb.tb_frame.f_lineno,
            'filename': tb.tb_frame.f_code.co_filename,
        })
    else:
        log.error(exc, extra={
            'lineno': tb.tb_frame.f_lineno,
            'filename': tb.tb_frame.f_code.co_filename,
        })
        return callback[0](*callback[1])


def get_exception_status_code(exc):

    if isinstance(exc, aiohttp.ClientError):
        if hasattr(exc, 'status'):
            return exc.status
        elif hasattr(exc, 'status_code'):
            return exc.status_code
        else:
            return None
    else:
        return None


def get_exception_request_method(exc):

    if isinstance(exc, aiohttp.ClientError):
        if hasattr(exc, 'request_info'):
            if exc.request_info.method:
                return exc.request_info.method
    return None


def get_exception_message(exc):
    if isinstance(exc, OSError):
        if hasattr(exc, 'strerror'):
            return exc.strerror

    message = getattr(exc, 'message', None) or str(exc)
    if message == "" or message is None:
        return exc.__class__.__name__
    return message
