from .base import AbstractGroup
from .items import Item, Separator, LabeledItem, ListItem, LabelMixin
from ..utils import get_log_value


__all__ = (
    'Line',
    'Lines',
    'LabeledLine',
    'LabeledLines',
    'List',
)


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
            self.value,
        ]


class Lines(AbstractGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    spacer = "\n"
    child_cls = (Line, 'Lines', Separator, 'List', 'LabeledLines', 'LabeledLine')

    def __init__(self, *children, **kwargs):
        kwargs.setdefault('lines_above', 1)
        super(Lines, self).__init__(*children, **kwargs)

    @property
    def components(self):
        return [
            self.header,
            self.indentation,
            self.value
        ]


class LabeledLine(Line, LabelMixin):

    child_cls = (Item, )

    def __init__(self, *children, label=None, label_formatter=None, label_delimiter=None, **kwargs):
        super(LabeledLine, self).__init__(*children, **kwargs)
        LabelMixin.__init__(self,
            label=label,
            label_formatter=label_formatter,
            label_delimiter=label_delimiter)

    @property
    def components(self):
        return [
            self.header,
            self.indentation,
            self.line_index,
            self.label,
            self.value,
        ]


class LabeledLines(Lines, LabelMixin):

    child_cls = (LabeledItem, LabeledLine, )

    def __init__(self, *children, label=None, label_formatter=None, label_delimiter=None, **kwargs):
        super(LabeledLines, self).__init__(*children, **kwargs)
        LabelMixin.__init__(self,
            label=label,
            label_formatter=label_formatter,
            label_delimiter=label_delimiter)


class List(Lines):
    """
    A mixture of AbstractGroup and AbstractItem.

    Therefore, we have to manually handle the keyword arguments that are
    traditionally meant for individual items, but can pass upstream the keyword
    arguments that are meant for the `Lines` AbstractGroup.
    """
    child_cls = (ListItem, )

    def __init__(self, value=None, **kwargs):
        children = []
        self.value = value
        super(List, self).__init__(*tuple(children), **kwargs)

    def formatted_value(self, record):
        return self.spacer.join([
            child(record) for child in self.valid_children(record)
        ])

    def valid_children(self, record):
        # This is the part of the logger with the new component system that is
        # not working.
        return []

        children = get_log_value(self.value, record)
        if children:
            return [
                ListItem(
                    it,
                    line_index=i + 1,
                    indent=self._indent,
                    formatter=self._formatter,
                    line_index_formatter=self._line_index_formatter
                ) for i, it in enumerate(children)
            ]
        return []
