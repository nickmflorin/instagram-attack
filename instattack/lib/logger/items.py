__all__ = (
    'LogItem',
    'LogItemLine',
    'LogItemLines',
)


class LogAbstractObject(object):
    """
    Used to specify additional properties on both groups of log items or
    individual log items.
    """

    def __init__(
        self,
        formatter=None,
        prefix=None,
        prefix_formatter=None,
        suffix=None,
        suffix_formatter=None,
        label=None,
        label_formatter=None,
        line_index=None,
        line_index_formatter=None,
        indent=None,
    ):

        from .formats import RecordAttributes

        self._formatter = formatter

        self._prefix_formatter = prefix_formatter
        self._prefix = prefix

        self._suffix_formatter = suffix_formatter
        self._suffix = suffix

        self._label = label
        self._label_formatter = label_formatter or RecordAttributes.LABEL

        self._line_index = line_index
        self._line_index_formatter = line_index_formatter or RecordAttributes.LINE_INDEX

        self._indent = indent

    def _format_value(self, value, formatter=None):
        if formatter:
            try:
                return formatter(value)
            except TypeError:
                value = "%s" % value
                return formatter(value)
        return value

    @property
    def indentation(self):
        if not self._indent:
            return ""
        return " " * self._indent

    @property
    def prefix(self):
        if not self._prefix:
            return ""
        return self._format_value(self._prefix, formatter=self._prefix_formatter)

    @property
    def suffix(self):
        if not self._suffix:
            return ""
        return self._format_value(self._suffix, formatter=self._suffix_formatter)

    @property
    def label(self):
        if not self._label:
            return ""
        return self._format_value(self._label, formatter=self._label_formatter)

    @property
    def line_index(self):
        if not self._line_index:
            return ""
        return self._format_value(self._line_index, formatter=self._line_index_formatter)


class LogItem(LogAbstractObject):

    def __init__(self, id, **kwargs):
        self.id = id
        super(LogItem, self).__init__(**kwargs)

    def can_format(self, context):
        if context.get(self.id) is not None:
            return True
        return False

    def _raw_value(self, context):
        return context[self.id]

    def _formatted_value(self, context):
        value = self._raw_value(context)
        return self._format_value(value, formatter=self._formatter)

    def format(self, context):
        return "%s%s%s%s%s%s" % (
            self.indentation,
            self.line_index,
            self.label,
            self.prefix,
            self._formatted_value(context),
            self.suffix
        )


class LogItemGroup(LogAbstractObject):
    """
    Base class for a container of LogItems.  Not meant to be used directly
    but as an abstract class.
    """

    def __init__(self, *items, **kwargs):
        self.items = items
        super(LogItemGroup, self).__init__(**kwargs)

    def can_format(self, context):
        if any(context.get(id) is not None for id in [item.id for item in self.items]):
            return True
        return False

    def _formatted_items(self, context):
        """
        Returns an array of the formatted version of each item in the group,
        where items are excluded if they cannot be formatted (since the context
        is not provided).
        """
        formatted_items = []
        for item in self.items:
            if item.can_format(context):
                formatted_items.append(item.format(context))
        return formatted_items


class LogItemLine(LogItemGroup):
    """
    Displays a series of log items each on the same line in the display.
    """

    def _formatted_value(self, context):
        formatted_items = self._formatted_items(context)
        return " ".join(formatted_items)

    def format(self, context):
        return "%s%s%s%s" % (
            self.indentation,
            self.line_index,
            self.label,
            self._formatted_value(context),
        )


class LogItemLines(LogItemGroup):
    """
    Displays a series of log items each on a new line in the display.
    """

    def __init__(self, *items, **kwargs):
        super(LogItemLines, self).__init__(*items, **kwargs)
        self.newline = kwargs.pop('newline', True)

    def _formatted_value(self, context):
        formatted_items = self._formatted_items(context)

        value = "\n".join(formatted_items)
        if self.newline:
            return "\n" + value
        return value

    def format(self, context):
        return "%s%s" % (
            self.indentation,
            self._formatted_value(context),
        )
