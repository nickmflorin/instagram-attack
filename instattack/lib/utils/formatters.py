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


def percentage(num1, num2):
    return f"{'{0:.2f}'.format((num1 / num2 * 100))} %"


def progress(num1, num2):
    return f"{num1}/{num2} ({'{0:.2f} %)'.format((num1 / num2 * 100))}"


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
