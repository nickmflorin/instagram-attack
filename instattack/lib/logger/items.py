from .formats import RecordAttributes

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
        label_formatter=RecordAttributes.LABEL,
        line_index=None,
        line_index_formatter=RecordAttributes.LINE_INDEX,
        indent=None,
    ):

        self._formatter = formatter

        self._prefix_formatter = prefix_formatter
        self._prefix = prefix

        self._suffix_formatter = suffix_formatter
        self._suffix = suffix

        self._label = label
        self._label_formatter = label_formatter

        self._line_index = line_index
        self._line_index_formatter = line_index_formatter

        self._indent = indent

    def _format_value(self, value, formatter=None):
        if formatter:
            try:
                return formatter(value)
            except TypeError:
                value = "%s" % value
                return formatter(value)
        return value

    def indentation(self, context, **kwargs):
        if not self._indent:
            return ""
        return " " * self._indent

    def value(self, context, **kwargs):
        value = context[self.id]
        return self._format_value(
            value,
            formatter=self._formatter
        )

    def prefix(self, context, **kwargs):
        if not self._prefix:
            return ""
        return self._format_value(
            self._prefix,
            formatter=self._prefix_formatter
        )

    def suffix(self, context, **kwargs):
        if not self._suffix:
            return ""
        return self._format_value(self._suffix, formatter=self._suffix_formatter)

    def label(self, context, **kwargs):
        if not self._label:
            return ""
        return self._format_value(
            self._label,
            formatter=self._label_formatter
        )

    def line_index(self, context, **kwargs):
        if not self._line_index:
            return ""
        return self._format_value(
            self._line_index,
            formatter=self._line_index_formatter
        )


class LogItem(LogAbstractObject):

    def __init__(self, id, **kwargs):
        self.id = id
        super(LogItem, self).__init__(**kwargs)

    def can_format(self, context):
        if context.get(self.id) is not None:
            return True
        return False

    def suffix(self, context, **kwargs):
        # Don't use a suffix if the item is the last in a LogItemLine group.
        group = kwargs.get('group')
        if group and isinstance(group, LogItemLine):
            index = kwargs['index']
            if index == len(group.valid_items(context)) - 1:
                return ""
        return super(LogItem, self).suffix(context, **kwargs)

    def format(self, context, **kwargs):
        return "%s%s%s%s%s%s" % (
            self.indentation(context, **kwargs),
            self.line_index(context, **kwargs),
            self.label(context, **kwargs),
            self.prefix(context, **kwargs),
            self.value(context, **kwargs),
            self.suffix(context, **kwargs)
        )


class LogItemGroup(LogAbstractObject):
    """
    Base class for a container of LogItems.  Not meant to be used directly
    but as an abstract class.
    """

    def __init__(self, **kwargs):
        for child in self.children:
            if not isinstance(child, self.child_cls):
                raise ValueError(
                    f'All children of {self.__class__.__name__} '
                    f'must be instances of {self.child_cls.__name__}.'
                )
        super(LogItemGroup, self).__init__(**kwargs)

    @property
    def children(self):
        if isinstance(self, LogItemLine):
            return self.items
        else:
            return self.lines

    def can_format(self, context):
        if any(context.get(id) is not None for id in [item.id for item in self.children]):
            return True
        return False

    def valid_items(self, context):
        valid_items = []
        for index, item in enumerate(self.children):
            if item.can_format(context):
                valid_items.append(item)
        return valid_items

    def formatted_items(self, context):
        """
        Returns an array of the formatted version of each item in the group,
        where items are excluded if they cannot be formatted (since the context
        is not provided).
        """
        valid_items = self.valid_items(context)
        return [item.format(context, group=self, index=i)
            for i, item in enumerate(valid_items)]

    def value(self, context, **kwargs):
        formatted_items = self.formatted_items(context)
        value = self.spacer.join(formatted_items)
        if self.newline:
            return "\n" + value
        return value


class LogItemLine(LogItemGroup):
    """
    Displays a series of log items each on the same line in the display.
    """
    spacer = " "
    child_cls = LogItem

    def __init__(self, *items, **kwargs):
        self.newline = kwargs.pop('newline', False)
        self.items = items
        super(LogItemLine, self).__init__(**kwargs)

    def format(self, context, **kwargs):
        return "%s%s%s%s%s%s" % (
            self.indentation(context, **kwargs),
            self.line_index(context, **kwargs),
            self.label(context, **kwargs),
            self.prefix(context, **kwargs),
            self.value(context, **kwargs),
            self.suffix(context, **kwargs)
        )


class LogItemLines(LogItemGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    spacer = "\n"
    child_cls = LogItemLine

    def __init__(self, *lines, **kwargs):
        self.newline = kwargs.pop('newline', True)
        self.lines = lines
        super(LogItemLines, self).__init__(**kwargs)

    def format(self, context, **kwargs):
        return "%s%s" % (
            self.indentation(context, **kwargs),
            self.value(context, **kwargs),
        )
