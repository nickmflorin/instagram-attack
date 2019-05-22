from ..utils import humanize_list
from .components import (
    FormattableComponent, Indentation, Header, GroupFormattableComponent)

"""
TODO
----
Learn how to use pyparsing, it can be extremely useful.
from pyparsing import (
    Literal, Suppress, Combine, Optional, alphas, delimitedList, oneOf, nums)
"""


class AbstractObj(object):

    deliminator = ""

    def __init__(self, indent=None, line_index=None, line_index_formatter=None):

        self.line_index = FormattableComponent(line_index, formatter=line_index_formatter)
        self.indentation = Indentation(indent)

    def __call__(self, record):
        if self.valid(record):
            # Components will never be an empty list if the object is valid because
            # it will always contain at a minimum the formatted value.
            components = [
                comp(record)
                for comp in self.components if comp(record)
            ]
            return self._deliminate_components(components)

    def _deliminate_components(self, components):
        return self.deliminator.join(["%s" % element for element in components])


class AbstractItem(AbstractObj):
    """
    Used to specify additional properties on both groups of log items or
    individual log items.
    """

    def __init__(self, value=None, formatter=None, **kwargs):
        super(AbstractItem, self).__init__(**kwargs)
        self.value = FormattableComponent(value, formatter=formatter)

    def valid(self, record):
        return self.value.valid(record)


class AbstractGroup(AbstractObj):
    """
    Base class for a container of LogItems.  Not meant to be used directly
    but as an abstract class.
    """

    def __init__(self, *children, formatter=None, header_char=None, lines_above=0, lines_below=0,
            **kwargs):
        super(AbstractGroup, self).__init__(**kwargs)

        self.header = Header(self, char=header_char)
        self.value = GroupFormattableComponent(self, formatter=formatter)

        self.children = children
        self.lines_above = lines_above
        self.lines_below = lines_below

        self._validate_children()
        self._passthrough_to_children()

    def _deliminate_components(self, components):
        deliminated = super(AbstractGroup, self)._deliminate_components(components)
        lines_above = "\n" * self.lines_above
        lines_below = "\n" * self.lines_below
        return "%s%s%s" % (lines_above, deliminated, lines_below)

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

    def _passthrough_to_children(self):

        def pass_to_children(attr):
            for child in self.children:
                if not getattr(child, attr):
                    value = getattr(self, attr)
                    setattr(child, attr, value)

        # TODO:

        # if self._formatter:
        #     pass_to_children('_formatter')
        # if self._indent:
        #     for child in self.children:
        #         if not child._indent:
        #             child._indent = self._indent
        #         else:
        #             child._indent += self._indent

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
