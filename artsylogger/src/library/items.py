from .base import AbstractItem
from ..utils import get_log_value, get_formatter_value

__all__ = (
    'Separator',
    'Item',
    'LabeledItem',
    'ListItem',
)


class Separator(object):

    def __init__(self, string):
        self.string = string

    def __call__(self, record):
        return self.string

    def valid(self, record):
        return True


class Item(AbstractItem):

    @property
    def components(self):
        return [
            self.indentation,
            self.line_index,
            self.value,
        ]


class ListItem(Item):

    def __init__(self, value, **kwargs):
        self.value = value
        super(Item, self).__init__(**kwargs)


# TODO: Make Label Into Component Class
class LabelMixin(object):

    def __init__(self, label=None, label_formatter=None, label_delimiter=":"):
        self._label = label
        self._label_formatter = label_formatter
        self._label_delimiter = label_delimiter

    def label(self, record):
        value = get_log_value(self._label, record)
        if not value:
            return ""
        formatter = get_formatter_value(self._label_formatter, record)
        return self._format_component(
            "%s%s " % (value, self._label_delimiter),
            formatter=formatter,
        )


class LabeledItem(Item, LabelMixin):

    def __init__(self, label=None, label_formatter=None, label_delimiter=None, **kwargs):
        super(LabeledItem, self).__init__(**kwargs)
        LabelMixin.__init__(self,
            label=label,
            label_formatter=label_formatter,
            label_delimiter=label_delimiter)

    @property
    def components(self):
        return [
            self.indentation,
            self.line_index,
            self.label,
            self.value,
        ]
