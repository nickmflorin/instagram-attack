from plumbum.path import LocalPath

from instattack import settings


def get_app_stack_at(stack, step=1):
    frames = [
        frame for frame in stack
        if frame.filename.startswith(settings.APP_DIR)
    ]
    return frames[step]


def relative_to_root(path):

    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    # This only happens for the test.py file...  We should remove this conditional
    # when we do not need that functionality anymore.
    if settings.APP_NAME in path.parts:
        ind = path.parts.index(settings.APP_NAME)
        parts = path.parts[ind:]
        path = LocalPath(*parts)

    return settings.DIR_STR(path)


def percentage(num1, num2):
    return f"{'{0:.2f}'.format((num1 / num2 * 100))} %"


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


def humanize_list(value, callback=str, conjunction='and', oxford_comma=True):
    """
    Turns an interable list into a human readable string.
    >>> list = ['First', 'Second', 'Third', 'fourth']
    >>> humanize_list(list)
    u'First, Second, Third, and fourth'
    >>> humanize_list(list, conjunction='or')
    u'First, Second, Third, or fourth'
    """

    num = len(value)
    if num == 0:
        return ""
    elif num == 1:
        return callback(value[0])
    s = u", ".join(map(callback, value[:num - 1]))
    if len(value) >= 3 and oxford_comma is True:
        s += ","
    return "%s %s %s" % (s, conjunction, callback(value[num - 1]))
