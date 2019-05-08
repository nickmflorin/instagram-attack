import inspect


def get_exception_message(exc):
    if isinstance(exc, OSError):
        if hasattr(exc, 'strerror'):
            return exc.strerror

    message = getattr(exc, 'message', None) or str(exc)
    if message == "" or message is None:
        return exc.__class__.__name__
    return message


def get_caller(correction=None):
    frame = inspect.stack()[correction]

    func_name = frame[3]
    try:
        return frame[0].f_globals[func_name]
    except KeyError:
        try:
            return frame[0].f_locals[func_name]
        except KeyError:
            if 'self' in frame[0].f_locals:
                if hasattr(frame[0].f_locals['self'], func_name):
                    return getattr(frame[0].f_locals['self'], func_name)
            raise


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
