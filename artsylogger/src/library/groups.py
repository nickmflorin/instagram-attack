from .items import AbstractObj, Item, Header, FormattablePart
from ..utils import humanize_list


__all__ = (
    'Line',
    'Lines',
)


class FormattableGroupPart(FormattablePart):

    def base_value(self, record):
        if self.valid(record):
            children = self.owner.valid_children(record)

            if len(children) == 1:
                return children[0](record)
            else:
                return self.owner.separator.join(
                    [child(record) for child in children]
                )

    def valid(self, record):
        return len(self.owner.valid_children(record)) != 0


class AbstractGroup(AbstractObj):

    def __init__(self, *children, **kwargs):
        super(AbstractGroup, self).__init__(children=children, **kwargs)

    def _pre_init(self, header=None, lines_above=0, lines_below=0, **kwargs):
        super(AbstractGroup, self)._pre_init(**kwargs)

        self._lines_above = lines_above
        self._lines_below = lines_below

        self.header = header or Header.none()
        if isinstance(header, dict):
            self.header = Header(**header)

        self.base_part = FormattableGroupPart(formatter=kwargs.get('formatter'))

    def own_parts(self):
        super(AbstractGroup, self).own_parts()
        self.base_part.owner = self
        if self.header:
            self.header.owner = self

    def add_siblings(self, siblings):
        super(AbstractGroup, self).add_siblings(siblings)
        if self.header:
            self.header.siblings = siblings
        self.base_part.siblings = siblings

    def add_parent(self, parent, index):
        super(AbstractGroup, self).add_parent(parent, index)

        self.base_part.parent = parent
        if self.header:
            self.header.parent = parent

    def _post_init(self):
        super(AbstractGroup, self)._post_init()
        self._validate_children()

    def _deliminate_parts(self, parts):
        deliminated = super(AbstractGroup, self)._deliminate_parts(parts)
        lines_above = "\n" * self._lines_above
        lines_below = "\n" * self._lines_below
        return "%s%s%s" % (lines_above, deliminated, lines_below)

    def valid_children(self, record):
        valid = []
        for child in self.children:
            if child.valid(record):
                valid.append(child)
        return valid

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


class Line(AbstractGroup):
    """
    Displays a series of log items each on the same line in the display.
    """
    separator = " "
    child_cls = (Item, )

    @property
    def parts(self):
        return [
            self.indentation,
            self.line_index,
            self.label,
            self.base_part,
        ]


class Lines(AbstractGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    separator = "\n"
    child_cls = (Line, 'Lines',)

    @property
    def parts(self):
        return [
            self.header,
            self.line_index,
            self.label,
            self.base_part,
        ]
