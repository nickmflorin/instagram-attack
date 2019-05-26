from ..utils import (
    get_log_value, get_formatter_value, escape_ansi_string, string_format_tuple)


__all__ = (
    'Item',
    'Label',
    'LineIndex',
    'Header',
)


class Part(object):

    def __init__(self, value=None, constant=None):
        self.owner = None
        self.parent = None
        self.siblings = None

        self._value = value
        self._constant = constant

    def __call__(self, record):
        return self.base_value(record)

    @classmethod
    def none(cls):
        return cls()

    def valid(self, record):
        return self.base_value(record) is not None

    def base_value(self, record):
        if self._value:
            value = get_log_value(self._value, record)
            if value is not None:
                return value
        elif self._constant:
            return self._constant
        return None


class Indentation(Part):

    def __init__(self, value=None, constant=None):
        super(Indentation, self).__init__(constant=constant)
        self._value = value or 0  # Prevent None Type

    @classmethod
    def none(cls):
        return cls(value=0)

    def base_value(self, record):
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

    def _apply_prefix_suffix(self, val, record):

        prefix = self._prefix or ""
        suffix = self._suffix or ""

        index = self.owner.index
        if self.owner.parent and self.owner.parent.children:
            try:
                child_after = self.owner.parent.children[index + 1]
            except IndexError:
                pass
            else:
                if not child_after.valid(record):
                    suffix = ""

        return "%s%s%s" % (prefix, val, suffix)

    def formatted(self, record):
        """
        [x] TODO:
        --------
        This is causing bugs, owner.parent._formatter does not exist:
        >>> if not formatter and (self.owner.parent and self.owner.parent._formatter):
        >>>    formatter = self.owner.parent._formatter
        """
        if self.valid(record):
            formatted = self.base_value(record)
            formatter = get_formatter_value(self._formatter, record)
            if formatter:
                try:
                    formatted = formatter("%s" % formatted)
                except TypeError:
                    if isinstance(formatted, tuple):
                        formatted = string_format_tuple(formatted)
                        formatted = formatter(formatted)

            formatted = self._wrap(formatted)
            return self._apply_prefix_suffix(formatted, record)


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
            # [x] TODO: Make bracketing an optional parameter.
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

    def __init__(self, **kwargs):
        self._pre_init(**kwargs)
        self._post_init()

    def __call__(self, record):
        if self.valid(record):
            # Parts will never be an empty list if the object is valid because
            # it will always contain at a minimum the formatted value.
            parts = [
                part(record)
                for part in self.parts if part and part(record)
            ]
            return self._deliminate_parts(parts)

    def _pre_init(self, children=None, indent=None, line_index=None, label=None, formatter=None):
        self.parent = None
        self.index = 0
        self.siblings = None

        self.children = list(children or [])

        self._formatter = formatter

        self.indentation = Indentation(value=indent)

        self.line_index = line_index or LineIndex.none()
        if isinstance(line_index, dict):
            self.line_index = LineIndex(**line_index)

        self.label = label or Label.none()
        if isinstance(label, dict):
            self.label = Label(**label)

    def _post_init(self):
        self.parent_children()
        self.own_parts()

    def own_parts(self):
        self.indentation.owner = self
        self.line_index.owner = self
        self.label.parent = self

    def parent_children(self):
        for i, child in enumerate(self.children):
            child.add_parent(self, i)
            siblings = [sib for sib in self.children if sib != child]
            child.add_siblings(siblings)

    def add_siblings(self, siblings):
        self.siblings = siblings

    def add_parent(self, parent, index):
        self.parent = parent
        self.index = index

    def valid(self, record):
        return self.base_part.valid(record)

    def _deliminate_parts(self, parts):
        return "".join(["%s" % part for part in parts])

    @property
    def parts(self):
        return [
            self.line_index,
            self.label,
            self.base_part,
        ]


class Item(AbstractObj):

    def _pre_init(
        self,
        value=None,
        constant=None,
        prefix=None,
        suffix=None,
        wrapper=None,
        **kwargs
    ):
        super(Item, self)._pre_init(**kwargs)
        self.base_part = FormattablePart(
            value=value,
            constant=constant,
            formatter=kwargs.get('formatter'),
            prefix=prefix,
            suffix=suffix,
            wrapper=wrapper,
        )

    def own_parts(self):
        super(Item, self).own_parts()
        self.base_part.owner = self

    def add_siblings(self, siblings):
        super(Item, self).add_siblings(siblings)
        self.base_part.siblings = siblings

    def add_parent(self, parent, index):
        super(Item, self).add_parent(parent, index)
        self.base_part.parent = parent
