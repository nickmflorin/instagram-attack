def filtered_array(*items):
    array = []
    for item in items:
        if isinstance(item, tuple) and len(item) == 2:
            if item[1] is not None:
                array.append(item[0] % item[1])
        elif isinstance(item, tuple) and len(item) == 1:
            if item[0] is not None:
                array.append(item[0])
        else:
            if item is not None:
                array.append(item)
    return array


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
    from .http_exceptions import HttpException

    if not isinstance(exc, HttpException):
        return str(exc)
    else:
        message = getattr(exc, 'message', None) or str(exc)

        parts = filtered_array(*(
            message,
            get_http_exception_request_method(exc),
            ("[%s]", get_http_exception_status_code(exc)),
            ("Err No: %s", get_http_exception_err_no(exc)),
        ))
        return ' '.join(parts)
