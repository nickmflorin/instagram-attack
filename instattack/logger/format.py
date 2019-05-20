from plumbum import colors


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

    def without_text_decoration(self):
        undecorated = [c for c in self.colors
            if c not in [colors.underline, colors.bold]]
        return Format(
            *undecorated,
            wrapper=self.wrapper,
            format_with_wrapper=self.format_with_wrapper
        )

    def without_wrapping(self):
        return Format(
            *self.colors,
        )
