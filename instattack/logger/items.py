from collections import Iterable
from .formats import RecordAttributes

__all__ = (
    'LogItem',
    'LogItemLine',
    'LogItemLines',
)


def get_off_record_obj(record, param):
    """
    Priorities overridden values explicitly provided in extra, and will
    check record.extra['context'] if the value is not in 'extra'.

    If tier_key is provided and item found is object based, it will try
    to use the tier_key to get a non-object based value.
    """
    if "." in param:
        parts = param.split(".")
        if len(parts) > 1:
            if hasattr(record, parts[0]):
                return get_off_record_obj(record, '.'.join(parts[1:]))
            else:
                return None
        else:
            if hasattr(record, parts[0]):
                return getattr(record, parts[0])
    else:
        if hasattr(record, param):
            return getattr(record, param)
        return None


def get_value(record, params=None, getter=None):

    def sort_priority(param):
        return param.count(".")

    if params:
        if isinstance(params, str):
            params = [params]
        params = sorted(params, key=sort_priority)

        # Here, each param can be something like "context.index", or "index"
        # Higher priority is given to less deeply nested versions.
        for param in params:
            value = get_off_record_obj(record, param)
            if value:
                return value
    else:
        return getter(record)


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

    def indentation(self, record, **kwargs):
        if not self._indent:
            return ""
        return " " * self._indent

    def value(self, record, **kwargs):
        value = get_value(record, params=self.params, getter=self.getter)
        if value:
            return self._format_value(
                value,
                formatter=self._formatter
            )

    def prefix(self, record, **kwargs):
        if not self._prefix:
            return ""
        return self._format_value(
            self._prefix,
            formatter=self._prefix_formatter
        )

    def suffix(self, record, **kwargs):
        if not self._suffix:
            return ""
        return self._format_value(self._suffix, formatter=self._suffix_formatter)

    def label(self, record, **kwargs):
        if not self._label:
            return ""
        return self._format_value(
            self._label,
            formatter=self._label_formatter
        )

    def line_index(self, record, **kwargs):
        if not self._line_index:
            return ""
        return self._format_value(
            self._line_index,
            formatter=self._line_index_formatter
        )


class LogItem(LogAbstractObject):

    def __init__(self, params=None, getter=None, **kwargs):
        self.params = params
        self.getter = getter
        super(LogItem, self).__init__(**kwargs)

    def suffix(self, record, **kwargs):
        # Don't use a suffix if the item is the last in a LogItemLine group.
        group = kwargs.get('group')
        if group and isinstance(group, LogItemLine):
            index = kwargs['index']
            if index == len(group.valid_children(record)) - 1:
                return ""
        return super(LogItem, self).suffix(record, **kwargs)

    def format(self, record, **kwargs):
        return "%s%s%s%s%s%s" % (
            self.indentation(record, **kwargs),
            self.line_index(record, **kwargs),
            self.label(record, **kwargs),
            self.prefix(record, **kwargs),
            self.value(record, **kwargs),
            self.suffix(record, **kwargs)
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

    def valid_children(self, record):
        valid_children = []
        for index, item in enumerate(self.children):
            if item.value(record) is not None:
                valid_children.append(item)
        return valid_children

    def formatted_items(self, record):
        """
        Returns an array of the formatted version of each item in the group,
        where items are excluded if they cannot be formatted (since the record
        is not provided).
        """
        valid_children = self.valid_children(record)
        return [item.format(record, group=self, index=i)
            for i, item in enumerate(valid_children)]

    def value(self, record, **kwargs):
        if len(self.valid_children(record)) != 0:
            formatted_items = self.formatted_items(record)
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

    def format(self, record, **kwargs):
        return "%s%s%s%s%s%s" % (
            self.indentation(record, **kwargs),
            self.line_index(record, **kwargs),
            self.label(record, **kwargs),
            self.prefix(record, **kwargs),
            self.value(record, **kwargs),
            self.suffix(record, **kwargs)
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

    def format(self, record, **kwargs):
        return "%s%s" % (
            self.indentation(record, **kwargs),
            self.value(record, **kwargs),
        )
