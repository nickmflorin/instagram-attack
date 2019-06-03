from plumbum import colors
from enum import Enum


class Format(object):
    def __init__(self, *args, wrapper=None, format_with_wrapper=False):
        self.colors = args
        self.wrapper = wrapper
        self.format_with_wrapper = format_with_wrapper

    def __call__(self, text):

        if self.wrapper and self.format_with_wrapper:
            text = self.wrapper % text

        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        # Apply wrapper after styling so we don't style the wrapper.
        text = (c | text)

        if self.wrapper and not self.format_with_wrapper:
            text = self.wrapper % text
        return text

    def copy(self):
        return Format(
            *self.colors,
            wrapper=self.wrapper,
            format_with_wrapper=self.format_with_wrapper
        )

    def make_bold(self):
        if colors.bold not in self.colors:
            self.colors += (colors.bold, )

    def add_wrapper(self, wrapper, format_with_wrapper=False):
        self.wrapper = wrapper
        self.format_with_wrapper = format_with_wrapper

    def remove_wrapper(self):
        self.wrapper = None
        self.format_with_wrapper = False

    def without_text_decoration(self):
        undecorated = [c for c in self.colors
            if c not in [colors.underline, colors.bold]]
        return Format(
            *undecorated,
            wrapper=self.wrapper,
            format_with_wrapper=self.format_with_wrapper
        )

    def without_wrapping(self):
        return Format(*self.colors)


class ColorFormatter(Enum):

    def __init__(self, color):
        self._fmt = Format(color)

    def __call__(self, text, **kwargs):
        if kwargs:
            fmt = self.format(**kwargs)
            return fmt(text)
        return self._fmt(text)

    def format(self, **kwargs):
        return self._adjust_format(**kwargs)

    def without_text_decoration(self):
        return self._fmt.without_text_decoration()

    def _adjust_format(self, bold=False, wrapper=None, format_with_wrapper=True):
        fmt = self._fmt.copy()
        if bold:
            fmt.make_bold()
        if wrapper:
            fmt.add_wrapper(wrapper, format_with_wrapper=format_with_wrapper)
        else:
            fmt.remove_wrapper()
        return fmt

    @property
    def raw(self):
        return str(self.value)

    @classmethod
    def custom(cls, color, **kwargs):

        class CustomColors(ColorFormatter):
            CUSTOM = colors.fg(color)

        return CustomColors.CUSTOM

    @classmethod
    def gray(cls, num, **kwargs):
        color_name = 'Grey%s' % num
        return cls.custom(color_name)


class AttributeFormatter(ColorFormatter):

    def __init__(self, *args):
        self._fmt = args[0]

    @property
    def colors(self):
        return self.format.colors
