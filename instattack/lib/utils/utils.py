import aiohttp
from plumbum import colors


class Format(object):
    def __init__(self, *args, wrapper=None):
        self.colors = args
        self.wrapper = wrapper

    def __call__(self, text):
        # TODO: Figure out how to dynamically create color tuples.
        if self.wrapper:
            text = self.wrapper % text

        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        return (c | text)


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


def is_numeric(value):
    try:
        float(value)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return None
    else:
        try:
            return int(value)
        except ValueError:
            return float(value)
        else:
            if float(value) == int(value):
                return int(value)
            return float(value)
