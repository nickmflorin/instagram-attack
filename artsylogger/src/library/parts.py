from ..utils import (
    get_log_value, is_record_callable, escape_ansi_string, string_format_tuple)


__all__ = (
    'Header',
    'LineIndex',
    'Label',
    'Indentation',
)


class Part(object):

    def __init__(self, value=None, constant=None):
        self._value = value
        self._constant = constant

    def __call__(self, record, owner):
        if self.valid(record, owner):
            return self.output(record, owner)

    def output(self, record, owner):
        return self.unformatted_value(record, owner)

    def unformatted_value(self, record, owner):
        if self._value:
            value = get_log_value(self._value, record)
            if value is not None:
                return value
        elif self._constant:
            return self._constant
        return None

    def valid(self, record, owner):
        return self.unformatted_value(record, owner) is not None

    @classmethod
    def none(cls):
        return cls()


class Indentation(Part):

    def valid(self, record, owner):
        return self._value is not None

    def unformatted_value(self, record, owner):
        """
        Trying to Add Parent Indent to Children Causing Lots of Problems.
        This was the closest we got:

        >>> if isinstance(self.owner, Lines):
        >>>    for i, child in enumerate(self.owner.children):
        >>>        if isinstance(child, Line):
        >>>            child.indentation._value += self._value
        >>>        else:
        >>>            print('Removing Indent %s' % self._value)
        >>>            child.indentation._value -= self._value
        >>>    return 0.0

        This works fine unless it is nested Lines in Lines...
        The following will indent each line 4 spaces instead of 2:
        >>> Lines(Lines([Line, Line], indent=2))

        For now, we will just explicitly set indentation for Line objects only.
        """
        return " " * self._value

    @classmethod
    def none(cls):
        return cls(value=0)


class FormattablePart(Part):

    def __init__(self, format=None, **kwargs):
        super(FormattablePart, self).__init__(**kwargs)
        self._format = format

    def output(self, record, owner):
        return self.formatted(record, owner)

    def format(self, record, owner):
        if self._format is not None:
            if callable(self._format):
                if is_record_callable(self._format):
                    return self._format(record)
                else:
                    return self._format
            return self._format

    def formatted(self, record, owner):
        """
        [x] TODO:
        --------
        This is causing bugs, owner.parent._formatter does not exist:
        >>> if not formatter and (self.owner.parent and self.owner.parent._formatter):
        >>>    formatter = self.owner.parent._formatter
        """
        unformatted = self.unformatted_value(record, owner)
        formatter = self.format(record, owner)
        if formatter:
            try:
                formatted = formatter("%s" % unformatted)
            except TypeError:
                if isinstance(unformatted, tuple):
                    unformatted = string_format_tuple(unformatted)
                    formatted = formatter(unformatted)
                else:
                    raise
            return formatted
        else:
            return unformatted


class ItemValue(FormattablePart):

    def __init__(self, prefix=None, suffix=None, **kwargs):
        super(ItemValue, self).__init__(**kwargs)
        self._prefix = prefix
        self._suffix = suffix

    def _apply_prefix_suffix(self, val, record, owner):

        prefix = self._prefix or ""
        suffix = self._suffix or ""

        index = owner.index
        if owner.parent and owner.parent.children:
            try:
                child_after = owner.parent.children[index + 1]
            except IndexError:
                pass
            else:
                if not child_after.valid(record):
                    suffix = ""

        return "%s%s%s" % (prefix, val, suffix)

    def formatted(self, record, owner):
        formatted = super(ItemValue, self).formatted(record, owner)
        return self._apply_prefix_suffix(formatted, record, owner)


class Label(FormattablePart):

    def __init__(self, delimiter=":", **kwargs):
        super(Label, self).__init__(**kwargs)
        self._delimiter = delimiter

    def unformatted_value(self, record, owner):
        value = super(Label, self).unformatted_value(record, owner)
        if value:
            if self._delimiter:
                return f"{value}{self._delimiter} "
            return f"{value} "


class LineIndex(FormattablePart):

    def unformatted_value(self, record, owner):
        # [x] TODO: Make bracketing an optional parameter that is specified
        # with the format object.
        value = super(LineIndex, self).unformatted_value(record, owner)
        if value:
            return f"[{value}] "


class Header(FormattablePart):

    def __init__(self, char=None, format=None, label=None, length=None):
        super(Header, self).__init__(format=format)
        self._char = char
        self._length = length
        self._label = label

    def length(self, record, owner):
        if self._length:
            return self._length

        string = owner.valid_children(record)[0](record)
        escaped = escape_ansi_string(string)

        line_length = len(escaped)
        label = self.label(record, owner)
        if label:
            line_length = int(0.5 * (line_length - 2 - len(label)))

        return line_length

    def label(self, record, owner):
        if self._label:
            return self._label(record, owner)

    def line(self, record, owner):
        return self._char * self.length(record, owner)

    def valid(self, record, owner):
        return self._char is not None

    def formatted(self, record, owner):
        line = self.line(record, owner)
        formatter = self.format(record, owner)

        # Format Lines Separately of Label?
        if formatter:
            line = formatter(line)

        label = self.label(record, owner)
        if label:
            return f"{line} {label} {line}\n"
        return f"{line}\n"
