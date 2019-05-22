from ..utils import escape_ansi_string, get_log_value, get_formatter_value


class Component(object):

    def __init__(self, value):
        self._value = value

    def __call__(self, record):
        return self.value(record)

    def valid(self, record):
        return self.value(record) != ""

    def value(self, record):
        if self._value:
            value = get_log_value(self._value, record)
            if value:
                return value
        return ""


class Indentation(Component):

    def value(self, record):
        if not self._value:
            return ""
        return " " * self._value


class FormattableComponent(Component):

    def __init__(self, value, formatter=None):
        super(FormattableComponent, self).__init__(value)
        self._formatter = formatter

    def __call__(self, record):
        return self.formatted(record)

    def formatted(self, record):
        if not self.valid(record):
            return ""

        value = self.value(record)
        formatter = get_formatter_value(self._formatter, record)
        if value and formatter:
                return formatter("%s" % value)
        return value


class GroupComponent(Component):
    """
    Abstract Class
    --------------
    Cannot be used alone since it does not define an overriden value method,
    and the group components do not have a _value.
    """

    def __init__(self, group):
        """
        For group component, value is None.
        """
        self.group = group

    def valid(self, record):
        return self.group.valid(record)


class Header(GroupComponent):

    def __init__(self, group, char=None):
        super(Header, self).__init__(group)
        self.char = char

    def value(self, record):
        if self.char and self.group.valid(record):
            string = self.group.valid_children(record)[0](record)
            string = escape_ansi_string(string)
            return self.char * len(string) + "\n"
        else:
            return ""


class GroupFormattableComponent(GroupComponent):

    def __init__(self, group, formatter=None):
        super(GroupFormattableComponent, self).__init__(group)
        self._formatter = formatter

    def __call__(self, record):
        return self.formatted(record)

    def formatted(self, record):

        from .items import Separator

        if not self.valid(record):
            return None

        children = self.group.valid_children(record)
        value = ""
        for i, child in enumerate(children):
            if isinstance(child, Separator):
                value += child(record)
            else:
                if i != 0 and not isinstance(children[i - 1], Separator):
                    value += (self.group.spacer + child(record))
                else:
                    value += child(record)
        return value

