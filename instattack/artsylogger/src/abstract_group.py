from .abstract_item import AbstractItem
from .items import Separator
from .utils import escape_ansi_string


"""
TODO
----
Learn how to use pyparsing, it can be extremely useful.
from pyparsing import (
    Literal, Suppress, Combine, Optional, alphas, delimitedList, oneOf, nums)
"""


class AbstractGroup(AbstractItem):
    """
    Base class for a container of LogItems.  Not meant to be used directly
    but as an abstract class.
    """

    def __init__(self, *children, header_char=None, lines_above=0, lines_below=0, **kwargs):
        self.children = children

        self.header_char = header_char
        self.lines_above = lines_above
        self.lines_below = lines_below

        self._validate_children()
        super(AbstractGroup, self).__init__(**kwargs)

    def _validate_children(self):
        for child in self.children:
            if not isinstance(child, self.child_cls):
                humanized_children = [cls_.__name__ for cls_ in self.child_cls]
                humanized_children = ', '.join(humanized_children)
                raise ValueError(
                    f'All children of {self.__class__.__name__} '
                    f'must be instances of {humanized_children}.'
                )

    def vertical_deliminate(self, formatted):
        lines_above = "\n" * self.lines_above
        lines_below = "\n" * self.lines_below
        return "%s%s%s" % (lines_above, formatted, lines_below)

    def valid_children(self, record):
        valid = []
        for i, child in enumerate(self.children):
            if isinstance(child, Separator):
                previous_child = None
                next_child = None

                try:
                    previous_child = self.children[i - 1]
                except IndexError:
                    pass

                try:
                    next_child = self.children[i + 1]
                except IndexError:
                    pass

                if previous_child and not previous_child.valid(record):
                    continue
                if next_child and not next_child.valid(record):
                    continue
                valid.append(child)
            else:
                if child.valid(record):
                    valid.append(child)

        return valid

    def valid(self, record):
        if len(self.valid_children(record)) != 0:
            return True
        return False

    def format(self, record):
        formatted = super(AbstractGroup, self).format(record)
        return self.vertical_deliminate(formatted)

    def header(self, record):
        if self.header_char and self.valid(record):
            string = self.valid_children(record)[0].format(record)
            string = escape_ansi_string(string)
            header = self.header_char * len(string) + "\n"
            return header

    def value(self, record):
        """
        TODO
        ----
        It is inconsistent to have the .format() method of the children being
        used with the .value() method of the parent.  We should make the format
        and value methods one method, to make it more consistent, and make grouping
        children easier.
        """
        if self.valid:
            value = ""
            children = self.valid_children(record)
            for i, child in enumerate(children):
                if isinstance(child, Separator):
                    value += child.format(record)
                else:
                    if i != 0 and not isinstance(children[i - 1], Separator):
                        value += (self.spacer + child.format(record))
                    else:
                        value += child.format(record)
            return value
