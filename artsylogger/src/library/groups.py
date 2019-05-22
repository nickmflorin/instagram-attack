from .items import AbstractObj, Item, Separator, Header, FormattablePart
from ..utils import humanize_list


__all__ = (
    'Line',
    'Lines',
)


class FormattableGroupPart(FormattablePart):

    def __init__(self, *children, formatter=None, separator=None):
        # TODO: Allow formatter to be passed through to children.
        # Will Format Over Children Components Currently
        super(FormattableGroupPart, self).__init__(formatter=formatter)
        self.children = children
        self._separator = separator

    def base_value(self, record):
        from .items import Separator

        if self.valid(record):
            children = self.valid_children(record)
            value = ""
            for i, child in enumerate(children):
                if isinstance(child, Separator):
                    value += child(record)
                else:
                    if i != 0 and not isinstance(children[i - 1], Separator):
                        value += (self._separator + child(record))
                    else:
                        value += child(record)
            return value

    def valid(self, record):
        return len(self.valid_children(record)) != 0

    def valid_children(self, record):
        from .items import Separator

        valid = []
        for previous_child, child, next_child in self._contextual_children():
            if isinstance(child, Separator):
                if previous_child and not previous_child.valid(record):
                    continue
                if next_child and not next_child.valid(record):
                    continue
                valid.append(child)
            else:
                if child(record) is not None:
                    valid.append(child)
        return valid

    def _contextual_children(self):
        """
        Generator that yields each child, their previous child and the next
        child as (previous, child, next).
        """
        for i, child in enumerate(self.children):
            previous_child = next_child = None
            try:
                previous_child = self.children[i - 1]
            except IndexError:
                pass
            try:
                next_child = self.children[i + 1]
            except IndexError:
                pass
            yield (previous_child, child, next_child)


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

        for child in children:
            # Separator Does Not Have Indentation
            if hasattr(child, 'indentation') and isinstance(child, AbstractGroup):
                child.indentation.add_from_parent(self)

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
    child_cls = (Item, Separator, 'Line', )


class Lines(AbstractGroup):
    """
    Displays a series of log items each on a new line in the display.
    """
    separator = "\n"
    child_cls = (Line, 'Lines', Separator, Item)

# class List(Lines):
#     """
#     A mixture of AbstractGroup and AbstractItem.

#     Therefore, we have to manually handle the keyword arguments that are
#     traditionally meant for individual items, but can pass upstream the keyword
#     arguments that are meant for the `Lines` AbstractGroup.
#     """
#     child_cls = (ListItem, )

#     def __init__(self, value=None, **kwargs):
#         children = []
#         self.value = value
#         super(List, self).__init__(*tuple(children), **kwargs)

#     def formatted_value(self, record):
#         return self.spacer.join([
#             child(record) for child in self.valid_children(record)
#         ])

#     def valid_children(self, record):
#         # This is the part of the logger with the new component system that is
#         # not working.
#         return []

#         children = get_log_value(self.value, record)
#         if children:
#             return [
#                 ListItem(
#                     it,
#                     line_index=i + 1,
#                     indent=self._indent,
#                     formatter=self._formatter,
#                     line_index_formatter=self._line_index_formatter
#                 ) for i, it in enumerate(children)
#             ]
#         return []
