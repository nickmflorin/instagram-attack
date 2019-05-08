from .formats import Format, RecordAttributes
from .http import get_exception_status_code, get_exception_request_method
from .err_handling import get_exception_message


__all__ = ('Format', )


def format_exception_message(exc, level):
    FORMAT_EXCEPTION_MESSAGE = LogItemLine(
        LogItem('method', formatter=RecordAttributes.METHOD),
        LogItem('message', formatter=level),
        LogItem('status_code', formatter=RecordAttributes.STATUS_CODE),
    )

    message = get_exception_message(exc)

    return FORMAT_EXCEPTION_MESSAGE.format(
        status_code=get_exception_status_code(exc),
        message=message,
        method=get_exception_request_method(exc)
    )


def format_log_message(msg, level, extra=None):
    extra = extra or {}
    if isinstance(msg, Exception):
        return format_exception_message(msg, level)
    else:
        if extra.get('highlight'):
            return LogItem('message',
                formatter=RecordAttributes.SPECIAL_MESSAGE).format(message=msg)
        return LogItem('message', formatter=Format(level.format.colors[0])).format(message=msg)


class LogAbstractItem(object):

    def __init__(self, prefix=None, suffix=None, formatter=None, indent=0):

        self.prefix = prefix
        self.suffix = suffix
        self.formatter = formatter
        self.indent = indent

    def format(self, **context):

        prefix = self.prefix or ""
        suffix = self.suffix or ""
        indentation = " " * self.indent

        value = self.value(**context)

        value = "%s%s%s" % (prefix, value, suffix)
        return "%s%s" % (indentation, value)


class LogAbstractItemSet(LogAbstractItem):

    def __init__(self, *items, **kwargs):
        self.items = items
        super(LogAbstractItemSet, self).__init__(**kwargs)

    def can_format(self, **context):
        if any(context.get(id) is not None for id in [item.id for item in self.items]):
            return True
        return False


class LogItem(LogAbstractItem):

    def __init__(self, id, **kwargs):
        self.id = id
        super(LogItem, self).__init__(**kwargs)

    def can_format(self, **context):
        if context.get(self.id) is not None:
            return True
        return False

    def value(self, **context):
        value = context[self.id]
        if self.formatter:
            try:
                new_value = self.formatter(value)
            except TypeError:
                value = "%s" % value
            else:
                return new_value
        return value


class LogLabeledItem(LogItem):

    def __init__(self, id, label=None, formatter=None, indent=0):

        prefix = None
        if label:
            prefix = RecordAttributes.LABEL(label)
            prefix = "%s: " % prefix

        super(LogLabeledItem, self).__init__(
            id,
            prefix=prefix,
            formatter=formatter,
            indent=indent
        )


class LogItemLine(LogAbstractItemSet):

    def value(self, **context):
        formatted_items = []
        for item in self.items:
            if item.can_format(**context):
                formatted_items.append(item.format(**context))
        return " ".join(formatted_items)


class LogItemSet(LogAbstractItemSet):

    def value(self, **context):
        formatted_items = []
        for item in self.items:
            if item.can_format(**context):
                formatted_items.append(item.format(**context))
        return "\n" + "\n".join(formatted_items)
