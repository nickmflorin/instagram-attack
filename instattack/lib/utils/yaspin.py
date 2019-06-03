import asyncio
from collections import Counter
import contextlib
import sys

from yaspin.core import Yaspin
from yaspin.helpers import to_unicode

from instattack.config import settings
from .terminal import cursor


class CustomYaspin(Yaspin):
    """
    Override of yaspin package to allow messages that are written for a given
    spinner to appear underneath the spinner, returning to the top of the block
    after each individual message and to the very bottom of the block when finished.

    New Behavior:
    -------------
    >>> [x] Loading
    >>>  > check
    >>>  > check2
    >>> (Cursor Position)

    Old Behavior:
    -------------
    >>>  > check
    >>>  > check2
    >>> [x] Loading
    >>> (Cursor Position)
    """

    INDENT_COLORS = {
        1: settings.Colors.GRAY,
        2: settings.Colors.MED_GRAY,
        3: settings.Colors.LIGHT_GRAY,
    }
    DEFAULT_INDEX_COLOR = settings.Colors.LIGHT_GRAY

    def __init__(self, numbered=False, *args, **kwargs):
        super(CustomYaspin, self).__init__(*args, **kwargs)
        self.current_indent = 1
        self.index_counter = Counter()
        self.numbered = numbered
        self.current_line = 1
        self.lines = 0

    def move_up(self, nlines):
        cursor.move_up(nlines=nlines)
        self.current_line -= nlines

    def move_down(self, nlines):
        cursor.move_down(nlines=nlines)
        self.current_line += nlines

    def start(self):
        self.current_line += 1
        self.lines += 1
        super(CustomYaspin, self).start()

    @contextlib.contextmanager
    def block(self):
        try:
            self.indent()
            yield
        finally:
            self.unindent()

    def indent(self):
        self.current_indent += 1

    def unindent(self):
        self.current_indent -= 1

    def number(self):
        self.numbered = True

    def stop(self):
        if self._dfl_sigmap:
            # Reset registered signal handlers to default ones
            self._reset_signal_handlers()

        if self._spin_thread:
            self._stop_spin.set()
            self._spin_thread.join()

        sys.stdout.write("\r")
        self._clear_line()

        if sys.stdout.isatty():
            self._show_cursor()

    @property
    def pointer(self):
        padding_before = " "
        if self.current_indent != 1:
            padding_before = "  "

        return padding_before + (" " * self.current_indent) + ">"

    @property
    def index(self):
        if self.numbered:
            index = self.index_counter[self.current_indent] + 1
            self.index_counter[self.current_indent] += 1
            index_string = "[%s]" % index
            return settings.Colors.GRAY(index_string)

    def get_write_message(self, text, failure=False, success=False):
        color = self.INDENT_COLORS.get(
            self.current_indent,
            self.DEFAULT_INDEX_COLOR
        )

        text = color(text)
        if failure:
            text = "%s %s" % (settings.Colors.GRAY("✘"), text)
        elif success:
            text = "%s %s" % (settings.Colors.GRAY("✔"), text)

        pointer = color(self.pointer)

        parts = [pointer, text]
        if self.index:
            parts = [pointer, self.index, text]

        message = " ".join(parts)
        message = to_unicode(message)
        return "{0}".format(message)


class SyncYaspin(CustomYaspin):

    def _freeze(self, final_text):
        """Stop spinner, compose last frame and 'freeze' it."""
        text = to_unicode(final_text)
        self._last_frame = self._compose_out(text, mode="last")

        # Should be stopped here, otherwise prints after
        # self._freeze call will mess up the spinner
        with self._stdout_lock:
            self.stop()
            sys.stdout.write(self._last_frame)
            self._show_cursor()

            # Add Break After Spinner by Not Going Down lines - 1
            self.move_down(self.lines)

    def write(self, text, indent=False, failure=False, success=False):
        """
        Write text in the terminal without breaking the spinner.
        """
        self.lines += 1
        if indent:
            self.indent()
        message = self.get_write_message(text, failure=failure, success=success)

        with self._stdout_lock:
            self.move_down(self.lines - 1)
            sys.stdout.write("{0}".format(message))
            self.move_up(self.lines - 1)


class AsyncYaspin(CustomYaspin):
    """
    This is currently not working because there are MANY private methods of
    Yaspin which use `with self._stdout_lock`, which would need to be converted
    to `async with self._stdout_lock`, which is time consuming.

    For now, we will just restrict the decorators and context managers utilizing
    this functionality to sync cases.
    """

    def __init__(self, *args, **kwargs):
        super(AsyncYaspin, self).__init__(*args, **kwargs)
        self._stdout_lock = asyncio.Lock()

    async def write(self, text, indent=False, break_after=False):
        """
        Write text in the terminal without breaking the spinner.
        """
        async with self._stdout_lock:
            sys.stdout.write("\r")
            self._clear_line()

            if indent:
                self.indent()

            message = self.get_write_message(text, break_after=break_after)
            sys.stdout.write("{0}".format(message))
