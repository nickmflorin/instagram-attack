from instattack.lib.utils import filtered_array


def get_http_exception_err_no(exc):
    if hasattr(exc, 'errno'):
        return exc.errno
    return None


def get_http_exception_status_code(exc):

    if hasattr(exc, 'status'):
        return exc.status
    elif hasattr(exc, 'status_code'):
        return exc.status_code
    else:
        return None


def get_http_exception_request_method(exc):

    if hasattr(exc, 'request_info'):
        if exc.request_info.method:
            return exc.request_info.method
    return None


def get_http_exception_message(exc):
    from .http import HttpException

    if isinstance(exc, HttpException):
        return str(exc)
    else:
        message = getattr(exc, 'message', None) or str(exc)
        if message is None or message == "":
            message = exc.__class__.__name__

        parts = filtered_array(*(
            message,
            get_http_exception_request_method(exc),
            ("[%s]", get_http_exception_status_code(exc)),
            ("Err No: %s", get_http_exception_err_no(exc)),
        ))
        return ' '.join(parts)
