from __future__ import absolute_import


class LogItem(str):

    def __new__(cls, *items, prefix=None, suffix=None, formatter=None, indent=0):
        items = ["%s" % item for item in items if item is not None]

        cls.indent = indent

        prefix = prefix or ""
        suffix = suffix or ""
        indentation = " " * cls.indent

        item = " ".join(items)
        if formatter:
            item = formatter.format(item)

        item = "%s%s%s" % (prefix, item, suffix)
        item = "%s%s" % (indentation, item)
        return str.__new__(cls, item)


class LogFormattedLine(LogItem):

    def __new__(cls, *items, **kwargs):
        items = ["%s" % item for item in items if item is not None]
        content = " ".join(items)
        return LogItem.__new__(cls, "%s" % content, **kwargs)


class LogLabeledItem(LogItem):
    def __new__(cls, item, label=None, formatter=None, indent=0):
        from .formats import RecordAttributes
        prefix = RecordAttributes.LABEL.format(label)
        prefix = "%s: " % prefix
        return LogFormattedLine.__new__(cls, item, prefix=prefix,
            formatter=formatter, indent=indent)


class LogFormattedString(str):

    def __new__(cls, *items):
        items = ["%s" % item for item in items if item is not None]
        return str.__new__(cls, "".join(items))
