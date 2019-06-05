from .utils import humanize_list
from .parts import Indentation, Label, Header, LineIndex, ItemValue


__all__ = ('Item', 'Line', 'Lines')


class AbstractObj(object):

    separator = ""

    def __init__(self, indent=None, line_index=None, label=None):

        self.index = 0
        self.parent = None
        self.siblings = None

        self.indentation = Indentation(value=indent or 0)
        self.line_index = line_index or LineIndex.none()
        self.label = label or Label.none()

    def __call__(self, record):
        if self.valid(record):
            parts = [part(record, self) for part in self.decorated_parts]
            parts = [pt for pt in parts if pt is not None]

            # Value of Abstract Item is Part Instance
            parts.append(self.value(record, self))

            indentation = self.indentation(record, self)
            if indentation:
                return indentation + self._deliminate_parts(parts)
            return self._deliminate_parts(parts)

    def add_siblings(self, siblings):
        self.siblings = siblings

    def add_parent(self, parent, index):
        self.parent = parent
        self.index = index

    def valid(self, record):
        return self.value.valid(record, self)

    def _deliminate_parts(self, parts):
        return "".join(["%s" % part for part in parts])


class AbstractGroup(AbstractObj):

    # For Now - Not allowing group to be set with a format attribute.
    def __init__(self, *children, header=None, lines_above=0, lines_below=0, **kwargs):  # noqa
        super(AbstractGroup, self).__init__(**kwargs)

        self._lines_above = lines_above
        self._lines_below = lines_below

        self.children = list(children or [])
        self.header = header or Header.none()

        self._validate_children()
        self._parent_children()

    def __call__(self, record):
        if self.valid(record):
            parts = [part(record, self) for part in self.decorated_parts]
            parts = [pt for pt in parts if pt is not None]

            # Value of Abstract Group is Method on Group
            parts.append(self.value(record))

            indentation = self.indentation(record, self)
            if indentation:
                return indentation + self._deliminate_parts(parts)

            return self._deliminate_parts(parts)

    def value(self, record):
        valid_children = self.valid_children(record)
        if len(valid_children) == 1:
            return valid_children[0](record)
        else:
            return self.separator.join(
                [child(record) for child in valid_children]
            )

    def _parent_children(self):
        for i, child in enumerate(self.children):
            child.add_parent(self, i)
            siblings = [sib for sib in self.children if sib != child]
            child.add_siblings(siblings)

    def _validate_children(self):
        humanized_children = [
            cls_.__name__ if not isinstance(cls_, str) else cls_
            for cls_ in self.child_cls
        ]
        for child in self.children:
            if child.__class__.__name__ not in humanized_children:
                humanized_children = humanize_list(humanized_children, conjunction='or')
                raise ValueError(
                    f'All children of {self.__class__.__name__} '
                    f'must be instances of {humanized_children}, not '
                    f'{child.__class__.__name__}.'
                )

    def _deliminate_parts(self, parts):
        deliminated = super(AbstractGroup, self)._deliminate_parts(parts)
        lines_above = "\n" * self._lines_above
        lines_below = "\n" * self._lines_below
        return "%s%s%s" % (lines_above, deliminated, lines_below)

    def valid(self, record):
        valid_children = self.valid_children(record)
        if len(valid_children) != 0:
            return True

    def valid_children(self, record):
        valid = []
        for child in self.children:
            if child.valid(record):
                valid.append(child)
        return valid


class Item(AbstractObj):

    def __init__(
        self,
        value=None,
        constant=None,
        prefix=None,
        suffix=None,
        format=None,
        show_missing=False,
        **kwargs
    ):
        super(Item, self).__init__(**kwargs)
        self.value = ItemValue(
            value=value,
            constant=constant,
            format=format,
            prefix=prefix,
            suffix=suffix,
            show_missing=show_missing,
        )

    @property
    def decorated_parts(self):
        return [
            self.line_index,
            self.label,
        ]


class Line(AbstractGroup):
    """
    Displays a series of log items each on the same line in the display.
    """
    separator = " "
    child_cls = (Item, )

    @property
    def decorated_parts(self):
        return [
            self.line_index,
            self.label,
        ]


class Lines(AbstractGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    separator = "\n"
    child_cls = (Line, 'Lines',)

    @property
    def decorated_parts(self):
        return [
            self.header,
            self.line_index,
            self.label,
        ]
