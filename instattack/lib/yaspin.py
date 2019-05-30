from collections import Counter
from yaspin.core import Yaspin

from instattack import settings


class CustomYaspin(Yaspin):

    def __init__(self, numbered=False, *args, **kwargs):
        super(CustomYaspin, self).__init__(*args, **kwargs)
        self.current_indent = 1
        self.index_counter = Counter()
        self.numbered = numbered

    def indent(self):
        self.current_indent += 1

    def number(self):
        self.numbered = True

    @property
    def pointer(self):
        pointer = " " + (" " * self.current_indent) + (">" * self.current_indent)
        return settings.Colors.ALT_GRAY(pointer)

    @property
    def index(self):
        if self.numbered:
            index = self.index_counter[self.current_indent] + 1
            self.index_counter[self.current_indent] += 1
            index_string = "[%s]" % index
            return settings.Colors.GRAY(index_string)

    def write(self, text, indent=False):
        if indent:
            self.indent()

        parts = [
            self.pointer,
            self.index,
            settings.Colors.MED_GRAY(text)
        ]
        parts = [pt for pt in parts if pt is not None]
        message = " ".join(parts)
        super(CustomYaspin, self).write(message)
