from .items import AbstractObj, Item, Header, FormattablePart
from ..utils import humanize_list


__all__ = (
    'Line',
    'Lines',
    'Group',
)


class FormattableGroupPart(FormattablePart):

    def __init__(self, *children, formatter=None, separator=None):
        # TODO: Allow formatter to be passed through to children.
        # Will Format Over Children Components Currently
        super(FormattableGroupPart, self).__init__(formatter=formatter)
        self.children = children
        self._separator = separator

    def base_value(self, record):
        if self.valid(record):
            children = self.valid_children(record)
            if len(children) == 1:
                return children[0](record)
            else:
                return self._separator.join([child(record) for child in children])

    def valid(self, record):
        return len(self.valid_children(record)) != 0

    def valid_children(self, record):
        valid = []
        for child in self.children:
            if child.valid(record):
                valid.append(child)
        return valid


class AbstractGroup(AbstractObj):

    def __init__(self, *children, formatter=None, header=None,
            lines_above=0, lines_below=0, **kwargs):
        super(AbstractGroup, self).__init__(**kwargs)

        self._validate_children(*children)
        self.base_part = FormattableGroupPart(
            *children,
            separator=self.separator,
            formatter=formatter
        )

        self.header = header
        if isinstance(header, dict):
            self.header = Header(**header)

        self._lines_above = lines_above
        self._lines_below = lines_below

        self._passthrough_to_children(*children)

    def _deliminate_parts(self, parts):
        deliminated = super(AbstractGroup, self)._deliminate_parts(parts)
        lines_above = "\n" * self._lines_above
        lines_below = "\n" * self._lines_below
        return "%s%s%s" % (lines_above, deliminated, lines_below)

    def _passthrough_to_children(self, *children):

        def pass_to_children(attr):
            for child in children:
                if not getattr(child.base_part, attr):
                    value = getattr(self.base_part, attr)
                    setattr(child.base_part, attr, value)

        if self.base_part._formatter:
            pass_to_children('_formatter')

    def _validate_children(self, *children):
        humanized_children = [
            cls_.__name__ if not isinstance(cls_, str) else cls_
            for cls_ in self.child_cls
        ]
        for child in children:
            if child.__class__.__name__ not in humanized_children:
                humanized_children = humanize_list(humanized_children, conjunction='or')
                raise ValueError(
                    f'All children of {self.__class__.__name__} '
                    f'must be instances of {humanized_children}, not '
                    f'{child.__class__.__name__}.'
                )

    @property
    def parts(self):
        return [
            self.header,
            self.indentation,
            self.line_index,
            self.label,
            self.base_part,
        ]


class Line(AbstractGroup):
    """
    Displays a series of log items each on the same line in the display.
    """
    separator = " "
    child_cls = (Item, )


class Group(AbstractGroup):
    """
    More flexible than Line since it allows us to group together Line and Lines
    objects and apply a common indent or format.
    """
    separator = ""
    child_cls = (Line, 'Lines')


class Lines(AbstractGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    separator = "\n"
    child_cls = (Line, 'Lines', Group)

    def _passthrough_to_children(self, *children):
        super(Lines, self)._passthrough_to_children(*children)

        # TODO:
        # There is a bug somewhere that is causing the first child of Lines to
        # automatically indent if indent is set on the parent.
        for child in children[1:]:
            if isinstance(child, AbstractGroup):
                child.indentation.add_from_parent(self)
