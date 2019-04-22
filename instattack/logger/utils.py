from __future__ import absolute_import

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
            value = self.formatter.format(value)
        return value


class LogLabeledItem(LogItem):

    def __init__(self, id, label=None, formatter=None, indent=0):
        from .formats import RecordAttributes

        prefix = None
        if label:
            prefix = RecordAttributes.LABEL.format(label)
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
