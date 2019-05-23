from ..utils import get_log_value, get_formatter_value, escape_ansi_string


__all__ = (
    'Item',
    'Label',
    'LineIndex',
    'Header',
)


class Part(object):

    def __init__(self, value=None, constant=None):
        self._value = value
        self._constant = constant

    def __call__(self, record):
        return self.base_value(record)

    def valid(self, record):
        return self.base_value(record) is not None

    def base_value(self, record):
        if self._value:
            value = get_log_value(self._value, record)
            if value:
                return value
        elif self._constant:
            return self._constant
        return None


class Indentation(Part):

    def base_value(self, record):
        if self._value:
            return " " * self._value

    def add_from_parent(self, parent):
        if self._value is None:
            self._value = parent.indentation._value
        elif parent.indentation._value is not None:
            self._value += parent.indentation._value


class FormattablePart(Part):

    def __init__(
        self,
        formatter=None,
        prefix=None,
        suffix=None,
        wrapper=None,
        **kwargs
    ):
        super(FormattablePart, self).__init__(**kwargs)
        self._formatter = formatter
        self._prefix = prefix
        self._suffix = suffix
        self._wrapper = wrapper

    def __call__(self, record):
        return self.formatted(record)

    def _wrap(self, val):
        if self._wrapper:
            return self._wrapper % val
        return val

    def _apply_prefix_suffix(self, val):
        """
        TODO
        ----
        Start passing in group and determine if the next item is valid before
        applying the suffix (like we used to with the Separator object).
        """
        prefix = self._prefix or ""
        suffix = self._suffix or ""
        return "%s%s%s" % (prefix, val, suffix)

    def formatted(self, record):
        if self.valid(record):
            formatted = self.base_value(record)

            formatter = get_formatter_value(self._formatter, record)
            if formatter:
                formatted = formatter("%s" % formatted)

            formatted = self._wrap(formatted)
            return self._apply_prefix_suffix(formatted)


class Label(FormattablePart):

    def __init__(self, delimiter=":", **kwargs):
        super(Label, self).__init__(**kwargs)
        self._delimiter = delimiter

    def base_value(self, record):
        value = super(Label, self).base_value(record)
        if value:
            if self._delimiter:
                return f"{value}{self._delimiter} "
            return f"{value} "


class LineIndex(FormattablePart):

    def base_value(self, record):
        value = super(LineIndex, self).base_value(record)
        if value:
            # TODO: Make bracketing an optional parameter.
            return f"[{value}] "


class Header(FormattablePart):

    def __init__(self, char=None, formatter=None, label=None, length=None):
        super(Header, self).__init__(formatter=formatter)
        self._char = char
        self._label = label
        self._length = length

    def length(self, record):
        if self._length:
            return self._length
        string = self.group.valid_children(record)[0](record)
        escaped = escape_ansi_string(string)

        line_length = len(escaped)
        label = self.label(record)
        if label:
            line_length = int(0.5 * (line_length - 2 - len(label)))

        return line_length

    def label(self, record):
        label = get_log_value(self._label, record)
        if not label:
            return self._label
        return label

    def line(self, record):
        if self.valid(record):
            return self._char * self.length(record)
        return ""

    def valid(self, record):
        return self._char is not None

    def base_value(self, record):
        if self.valid(record):
            line = self.line(record)
            label = self.label(record)
            if label:
                return f"{line} {label} {line}\n"
            return f"{line}\n"


class AbstractObj(object):

    separator = ""

    def __init__(self, indent=None, line_index=None, label=None):

        self.line_index = line_index
        if isinstance(line_index, dict):
            self.line_index = LineIndex(**line_index)

        self.label = label
        if isinstance(label, dict):
            self.label = Label(**label)

        self.indentation = Indentation(value=indent)

    def __call__(self, record):
        if self.valid(record):
            # Parts will never be an empty list if the object is valid because
            # it will always contain at a minimum the formatted value.
            parts = [
                part(record)
                for part in self.parts if part and part(record)
            ]
            return self._deliminate_parts(parts)

    def valid(self, record):
        return self.base_part.valid(record)

    def _deliminate_parts(self, parts):
        return "".join(["%s" % part for part in parts])

    @property
    def parts(self):
        return [
            self.indentation,
            self.line_index,
            self.label,
            self.base_part,
        ]


class Item(AbstractObj):

    def __init__(
        self,
        value=None,
        constant=None,
        formatter=None,
        prefix=None,
        suffix=None,
        wrapper=None,
        **kwargs
    ):
        super(Item, self).__init__(**kwargs)
        self.base_part = FormattablePart(
            value=value,
            constant=constant,
            formatter=formatter,
            prefix=prefix,
            suffix=suffix,
            wrapper=wrapper,
        )
