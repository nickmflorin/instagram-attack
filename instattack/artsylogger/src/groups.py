from .abstract_group import AbstractGroup
from .items import Item, Separator, LabeledItem, ListItem, LabelMixin
from .utils import get_record_attribute


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
            self.formatted_value,
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
            self.formatted_value
        ]


class LabeledLine(Line, LabelMixin):

    def __init__(self, label=None, label_formatter=None, label_delimiter=None, **kwargs):
        super(LabeledLine, self).__init__(**kwargs)
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
            self.formatted_value,
        ]


class LabeledLines(Lines):

    child_cls = (LabeledItem, )


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

    def formatted_value(self, record):
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
