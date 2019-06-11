from collections import Counter
import contextlib
from datetime import datetime
from enum import Enum
import shutil
import sys
import time
from yaspin.core import Yaspin
from yaspin.helpers import to_unicode

from instattack.config import constants

from .terminal import cursor, measure_ansi_string


class SpinnerStates(Enum):

    OK = ("Ok", constants.Formats.State.SUCCESS)
    WARNING = ("Warning", constants.Formats.State.WARNING)
    FAIL = ("Failed", constants.Formats.State.FAIL)
    NOTSET = ("Not Set", constants.Formats.State.NOTSET)

    def __init__(self, desc, fmt):
        self.desc = desc
        self.fmt = fmt


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

    def __init__(self, text=None, numbered=False, *args, **kwargs):
        text = constants.Formats.Text.NORMAL(text)
        super(CustomYaspin, self).__init__(text=text, *args, **kwargs)

        self._current_indent = 0
        self._index_counter = Counter()
        self._numbered = numbered
        self._current_line = 1
        self._lines = 0

        self.state = SpinnerStates.NOTSET

    def start(self):
        self._current_line += 1
        self._lines += 1
        super(CustomYaspin, self).start()
        self.indent()

    def done(self):
        if self.state == SpinnerStates.NOTSET:
            self.state = SpinnerStates.OK
        # Freeze also calls stop.
        import time
        time.sleep(2)
        self._freeze()

    def warned(self):
        self.state = SpinnerStates.WARNING

    def error(self, error):
        self.state = SpinnerStates.FAIL

    def stop(self):
        # Reset registered signal handlers to default ones
        if self._dfl_sigmap:
            self._reset_signal_handlers()

        if self._spin_thread:
            self._stop_spin.set()
            self._spin_thread.join()

        sys.stdout.write("\r")
        self._clear_line()

    def warning(self, text):
        self.state = SpinnerStates.WARNING
        # text = constants.Formats.State.WARNING.without_icon()("Warning: %s" % text)
        self.write(text)

    def write(self, text, indent=False):
        """
        Write text in the terminal without breaking the spinner.
        """
        self._lines += 1
        if indent:
            self.indent()

        message = self._compose_out(text=text, pointed=True)

        with self._stdout_lock:
            self._move_down(self._lines - 1)
            sys.stdout.write(message)
            self._move_up(self._lines - 1)
            sys.stdout.write("\r")

    @contextlib.contextmanager
    def block(self):
        try:
            self.indent()
            yield
        finally:
            self.unindent()

    def indent(self):
        self._current_indent += 1

    def unindent(self):
        self._current_indent -= 1

    def number(self):
        self._numbered = True

    def _compose_out(self, frame=None, text=None, pointed=False):

        text = text or self._text

        parts = (
            self._line_start(pointed=pointed),
            self._index(),
            self._decorated_text(
                text=text,
                frame=frame,
                pointed=pointed,
            )
        )

        message = "".join(parts)
        date_message = constants.Formats.Text.FADED.with_wrapper("[%s]")(
            datetime.now().strftime(constants.DATE_FORMAT)
        )

        columns, _ = shutil.get_terminal_size(fallback=(80, 24))
        separated = (" " * (columns - 5 - measure_ansi_string(date_message) -
            measure_ansi_string(message)))

        return to_unicode("\r%s%s%s" % (message, separated, date_message))

    def _decorated_text(self, text, frame=None, pointed=False):
        """
        >>> ✔_Preparing                     -> Indentation 0
        >>> __> ✘_Something Happened         -> Indentation 0

        Decorated Text: ✔_Preparing
        Decorated Text: ✘_Something Happened
        """
        text_format = self.state.fmt
        if pointed:
            text_format = constants.Formats.Text.get_hierarchal_format(
                self._current_indent)

        if frame:
            if self._color_func:
                frame = self._color_func(frame)
            return "%s %s" % (frame, self.state.fmt.without_icon()(text))
        else:
            return text_format(text)

    def _line_start(self, pointed=False):
        """
        By default, the writing for each line technically starts after (2) spaces,
        one empty space reserved for an icon or frame and the next reserved
        to separate the icon or frame from the text.  The Line Start includes
        these two spaces for each indent index (when current_indent > 0)
        plus a pointer, "> ",

        >>> ✔_Preparing                     -> Indentation 0, Line Start: None
        >>> __>_Disabling_External_Loggers   -> Indentation 1, Line Start: __>_
        >>> __>_Setting_Up_Directories
        >>> ____>_First Step                 -> Indentation 2, Line Start: ____>_

        (Empty spaces denoted with "_")

        Any additional indentation is considered to be applied after this initial
        (2) space indentation that is reserved for icons and frames.  This
        makes our text line up nicely.
        """
        if pointed:
            indentation = "  " * self._current_indent
            pointer_color = constants.Formats.Pointer.get_hierarchal_format(self._current_indent)
            pointer = pointer_color("> ")
            return "%s%s" % (indentation, pointer)
        return ""

    def _index(self):
        if self._numbered:
            index = self._index_counter[self._current_indent] + 1
            self._index_counter[self._current_indent] += 1
            return constants.Formats.Wrapper.INDEX(index)
        return ""

    def _move_up(self, nlines):
        cursor.move_up(nlines=nlines)
        self._current_line -= nlines

    def _move_down(self, nlines):
        cursor.move_down(nlines=nlines)
        self._current_line += nlines

    def _spin(self):
        while not self._stop_spin.is_set():

            if self._hide_spin.is_set():
                # Wait a bit to avoid wasting cycles
                time.sleep(self._interval)
                continue

            spin_phase = next(self._cycle)
            out = self._compose_out(frame=spin_phase)

            with self._stdout_lock:
                sys.stdout.write(out)
                self._clear_line()
                sys.stdout.flush()

            time.sleep(self._interval)

    def _freeze(self):

        text = self._compose_out()

        # Should be stopped here, otherwise prints after
        # self._freeze call will mess up the spinner
        with self._stdout_lock:
            self.stop()
            sys.stdout.write(text)
            self._show_cursor()

            # Add Break After Spinner by Not Going Down lines - 1
            self._move_down(self._lines + 1)
