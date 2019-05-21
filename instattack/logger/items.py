import re
from .utils import get_record_attribute

__all__ = (
    'Item',
    'Separator',
    'Line',
    'Lines',
)

"""
TODO
----
Learn how to use pyparsing, it can be extremely useful.
from pyparsing import (
    Literal, Suppress, Combine, Optional, alphas, delimitedList, oneOf, nums)
"""


class AbstractObj(object):
    """
    Used to specify additional properties on both groups of log items or
    individual log items.
    """

    def __init__(
        self,
        formatter=None,
        label=None,
        line_index=None,
        indent=None,
        line_index_formatter=None,
    ):
        from .constants import RecordAttributes
        self._formatter = formatter

        self._label = label
        self._label_formatter = RecordAttributes.LABEL

        self._line_index = line_index
        self._line_index_formatter = RecordAttributes.LINE_INDEX or line_index_formatter

        self._indent = indent

    def indentation(self, record, **kwargs):
        # Component
        if not self._indent:
            return ""
        return " " * self._indent

    def label(self, record, **kwargs):
        # Component
        if not self._label:
            return ""
        return self._format_component(
            self._label,
            formatter=self._label_formatter
        )

    def line_index(self, record, **kwargs):
        # Component
        if not self._line_index:
            return ""
        return self._format_component(
            self._line_index,
            formatter=self._line_index_formatter
        )

    def _format_component(self, value, formatter=None):
        if formatter:
            try:
                return formatter(value)
            except TypeError:
                value = "%s" % value
                return formatter(value)
        return value

    def format(self, record):
        created = [comp(record) for comp in self.components if comp(record) is not None]
        formatted = "".join(["%s" % comp for comp in created])
        return formatted


class AbstractGroup(AbstractObj):
    """
    Base class for a container of LogItems.  Not meant to be used directly
    but as an abstract class.
    """

    def __init__(self, *children, **kwargs):
        self.children = children
        self.header_char = kwargs.pop('header_char', None)
        self.lines_above = kwargs.pop('lines_above', 0)
        self.lines_below = kwargs.pop('lines_below', 0)

        for child in self.children:
            if not isinstance(child, self.child_cls):
                humanized_children = [cls_.__name__ for cls_ in self.child_cls]
                humanized_children = ', '.join(humanized_children)
                raise ValueError(
                    f'All children of {self.__class__.__name__} '
                    f'must be instances of {humanized_children}.'
                )
        super(AbstractGroup, self).__init__(**kwargs)

    def vertical_deliminate(self, formatted):
        lines_above = "\n" * self.lines_above
        lines_below = "\n" * self.lines_below
        return "%s%s%s" % (lines_above, formatted, lines_below)

    def valid_children(self, record):
        valid = []
        for i, child in enumerate(self.children):
            if isinstance(child, Separator):
                previous_child = None
                next_child = None

                try:
                    previous_child = self.children[i - 1]
                except IndexError:
                    pass

                try:
                    next_child = self.children[i + 1]
                except IndexError:
                    pass

                if previous_child and not previous_child.valid(record):
                    continue
                if next_child and not next_child.valid(record):
                    continue
                valid.append(child)
            else:
                if child.valid(record):
                    valid.append(child)

        return valid

    def valid(self, record):
        if len(self.valid_children(record)) != 0:
            return True
        return False

    def format(self, record):
        formatted = super(AbstractGroup, self).format(record)
        return self.vertical_deliminate(formatted)

    def header(self, record):
        if self.header_char and self.valid(record):
            string = self.valid_children(record)[0].format(record)
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            string = ansi_escape.sub('', string)

            header = self.header_char * len(string) + "\n"
            return header

    def value(self, record):
        """
        TODO
        ----
        It is inconsistent to have the .format() method of the children being
        used with the .value() method of the parent.  We should make the format
        and value methods one method, to make it more consistent, and make grouping
        children easier.
        """
        if self.valid:
            value = ""
            children = self.valid_children(record)
            for i, child in enumerate(children):
                if isinstance(child, Separator):
                    value += child.format(record)
                else:
                    if i != 0 and not isinstance(children[i - 1], Separator):
                        value += (self.spacer + child.format(record))
                    else:
                        value += child.format(record)
            return value


class Separator(object):

    def __init__(self, string):
        self.string = string

    def format(self, record):
        return self.string

    def valid(self, record):
        return True


class Item(AbstractObj):

    def __init__(self, params=None, getter=None, **kwargs):
        self.params = params
        self.getter = getter
        super(Item, self).__init__(**kwargs)

    def valid(self, record):
        return self.value(record) is not None

    def value(self, record):
        value = get_record_attribute(record, params=self.params, getter=self.getter)
        if value is not None:
            return self._format_component(
                value,
                formatter=self._formatter
            )

    @property
    def components(self):
        return [
            self.indentation,
            self.line_index,
            self.label,
            self.value,
        ]


class Line(AbstractGroup):
    """
    Displays a series of log items each on the same line in the display.
    """
    spacer = " "
    child_cls = (Item, Separator, )

    @property
    def components(self):
        return [
            self.header,
            self.indentation,
            self.line_index,
            self.label,
            self.value,
        ]


class Lines(AbstractGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    spacer = "\n"

    def __init__(self, *children, **kwargs):
        self.child_cls = (Line, Lines, Separator, List, )
        kwargs.setdefault('lines_above', 1)
        super(Lines, self).__init__(*children, **kwargs)

    @property
    def components(self):
        return [
            self.header,
            self.indentation,
            self.value
        ]


class ListItem(Item):

    def __init__(self, value, **kwargs):
        self._value = value
        super(Item, self).__init__(**kwargs)

    def value(self, record):
        return self._value

    @property
    def components(self):
        return [
            self.indentation,
            self.line_index,
            self.value,
        ]


class List(Lines):
    """
    A mixture of AbstractGroup and AbstractItem.

    Therefore, we have to manually handle the keyword arguments that are
    traditionally meant for individual items, but can pass upstream the keyword
    arguments that are meant for the `Lines` AbstractGroup.
    """
    child_cls = (ListItem, )

    def __init__(self, params, indent=None, formatter=None, line_index_formatter=None, **kwargs):
        self.params = params
        self.formatter = formatter
        self.indent = indent
        self.line_index_formatter = line_index_formatter
        super(List, self).__init__(**kwargs)

    def value(self, record):
        return self.spacer.join([child.format(record) for child in self.valid_children(record)])

    def valid_children(self, record):
        children = get_record_attribute(record, params=self.params)
        if children:
            return [
                ListItem(
                    it,
                    line_index=i + 1,
                    indent=self.indent,
                    formatter=self.formatter,
                    line_index_formatter=self.line_index_formatter
                ) for i, it in enumerate(children)
            ]
        return []
