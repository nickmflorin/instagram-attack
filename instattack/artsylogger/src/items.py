from .abstract_item import AbstractItem
from .utils import get_record_attribute


__all__ = (
    'Separator',
    'Item',
    'LabeledItem',
    'ListItem',
)


class Separator(object):

    def __init__(self, string):
        self.string = string

    def format(self, record):
        return self.string

    def valid(self, record):
        return True


class Item(AbstractItem):

    def __init__(self, params=None, getter=None, **kwargs):
        self.params = params
        self.getter = getter
        super(Item, self).__init__(**kwargs)

    def valid(self, record):
        return self.value(record) is not None

    def value(self, record):
        return get_record_attribute(record, params=self.params, getter=self.getter)

    def formatted_value(self, record):
        value = self.value(record)
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
            self.formatted_value,
        ]


class LabelMixin(object):

    def __init__(self, label=None, label_formatter=None, label_delimiter=":"):
        self._label = label
        self._label_formatter = label_formatter
        self._label_delimiter = label_delimiter

    def label(self, record):
        # Component
        if not self._label:
            return ""
        return self._format_component(
            "%s%s " % self._label_delimiter,
            formatter=self._label_formatter
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
            self.formatted_value,
        ]


class ListItem(Item):

    def __init__(self, value, **kwargs):
        self._value = value
        super(Item, self).__init__(**kwargs)

    def formatted_value(self, record):
        return self._value
