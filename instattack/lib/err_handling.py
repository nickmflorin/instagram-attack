import aiohttp
import inspect


def get_exception_message(exc):
    if isinstance(exc, OSError):
        if hasattr(exc, 'strerror'):
            return exc.strerror

    message = getattr(exc, 'message', None) or str(exc)
    if message == "" or message is None:
        return exc.__class__.__name__
    return message


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


def is_async_func(f):
    if any([inspect.iscoroutinefunction(f),
            inspect.isgeneratorfunction(f),
            inspect.iscoroutine(f),
            inspect.isawaitable(f),
            inspect.isasyncgenfunction(f),
            inspect.isasyncgen(f)]):
        return True
    else:
        return False


def is_async_caller(log):

    # Get the calling frame
    caller = inspect.currentframe().f_back.f_back.f_back

    # Pull the function name from FrameInfo
    func_name = inspect.getframeinfo(caller)[2]
    log.critical('Checking Async : %s' % func_name)

    # Get the function object
    f = caller.f_locals.get(
        func_name,
        caller.f_globals.get(func_name)
    )
    # If the functino does not exist, it might be a method.
    if not f:
        if 'self' in caller.f_locals:
            f = getattr(caller.f_locals['self'], func_name)
            log.critical('Is method')
    else:
        log.critical('is not method')

    # If there's any indication that the function object is a
    # coroutine, return True. inspect.iscoroutinefunction() should
    # be all we need, the rest are here to illustrate.
    if any([inspect.iscoroutinefunction(f),
            inspect.isgeneratorfunction(f),
            inspect.iscoroutine(f),
            inspect.isawaitable(f),
            inspect.isasyncgenfunction(f),
            inspect.isasyncgen(f)]):
        log.critical('is async')
        return True
    else:
        log.critical('is not async')
        return False


# def get_caller(correction=None):
#     frame = inspect.stack()[correction]

#     func_name = frame[3]
#     try:
#         return frame[0].f_globals[func_name]
#     except KeyError:
#         try:
#             return frame[0].f_locals[func_name]
#         except KeyError:
#             if 'self' in frame[0].f_locals:
#                 if hasattr(frame[0].f_locals['self'], func_name):
#                     return getattr(frame[0].f_locals['self'], func_name)
#             raise


def tb_context(frame):
    return {
        'lineno': frame.lineno,
        'filename': frame.filename,
    }


def traceback_to(stack, back=0):
    try:
        frame = stack[back]
    except IndexError:
        raise ValueError('Not enough frames in stack.')
    else:
        return tb_context(frame)
