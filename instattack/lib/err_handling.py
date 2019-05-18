import aiohttp


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


def tb_context(frame):
    return {
        'lineno': frame.lineno,
        'filename': frame.filename,
        'funcName': frame.function,
    }


def traceback_to(stack, frame_correction=0):
    try:
        frame = stack[frame_correction]
    except IndexError:
        raise ValueError('Not enough frames in stack.')
    else:
        return tb_context(frame)
