from collections import Counter
import contextlib
from datetime import datetime
import shutil
import sys
import time
from yaspin.core import Yaspin
from yaspin.helpers import to_unicode

from instattack.config import constants

from .terminal import cursor, measure_ansi_string


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

    POINTER_COLORS = {
        1: constants.Colors.GRAY,
        2: constants.Colors.MED_GRAY,
        3: constants.Colors.LIGHT_GRAY,
    }
    STATE_COLORS = {
        (True, True, False): constants.Colors.GREEN,
        (True, False, False): constants.Colors.GREEN,
        (False, True, False): constants.Colors.RED,
        (False, False, True): constants.Colors.YELLOW,
        (False, False, False): constants.Colors.GRAY,
    }
    STATE_ICONS = {
        (True, False, False): "✔",
        (False, True, False): "✘",
        (False, False, True): "\u26A0",
        (False, False, False): "",
    }
    DEFAULT_POINTED_TEXT_COLOR = constants.Colors.LIGHT_GRAY
    DEFAULT_POINTED_ICON_COLOR = constants.Colors.MED_GRAY

    def __init__(self, numbered=False, *args, **kwargs):
        super(CustomYaspin, self).__init__(*args, **kwargs)

        self._current_indent = 0
        self._index_counter = Counter()
        self._numbered = numbered
        self._current_line = 1
        self._lines = 0

    def start(self):
        self._current_line += 1
        self._lines += 1
        super(CustomYaspin, self).start()
        self.indent()

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
        text = self.STATE_COLORS[(False, False, True)]("Warning: ") + text
        self.write(text, warning=True)

    def write(self, text, indent=False, failure=False, warning=False, success=False):
        """
        Write text in the terminal without breaking the spinner.
        """
        self._lines += 1
        if indent:
            self.indent()

        message = self._compose_out(
            text=text,
            failure=failure,
            success=success,
            warning=warning,
            pointed=True
        )

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

    def ok(self):
        self._freeze(success=True)

    def fail(self):
        self._freeze(failure=True)

    def indent(self):
        self._current_indent += 1

    def unindent(self):
        self._current_indent -= 1

    def number(self):
        self._numbered = True

    def _compose_out(self, frame=None, success=False, failure=False, warning=False,
            text=None, pointed=False):

        text = text or self._text
        icon = self.STATE_ICONS[(success, failure, warning)]

        text_color = icon_color = self.STATE_COLORS[(success, failure, warning)]
        if pointed:
            text_color = self.POINTER_COLORS.get(
                self._current_indent, self.DEFAULT_POINTED_TEXT_COLOR)

        parts = (
            self._line_start(pointed=pointed),
            self._index(),
            self._decorated_text(
                text=text,
                icon=icon,
                frame=frame,
                text_color=text_color,
                icon_color=icon_color,
            )
        )

        message = "".join(parts)
        date_message = constants.RecordAttributes.DATETIME(
            datetime.now().strftime(constants.DATE_FORMAT)
        )

        columns, _ = shutil.get_terminal_size(fallback=(80, 24))
        separated = (" " * (columns - 5 - measure_ansi_string(date_message) -
            measure_ansi_string(message)))

        return to_unicode("\r%s%s%s" % (message, separated, date_message))

    def _decorated_text(self, text, icon=None, frame=None, text_color=None, icon_color=None):
        """
        >>> ✔_Preparing                     -> Indentation 0
        >>> __> ✘_Something Happened         -> Indentation 0

        Decorated Text: ✔_Preparing
        Decorated Text: ✘_Something Happened
        """
        decorator = " "
        if text_color:
            text = text_color(text)

        if frame:
            decorator = frame
            if self._color_func:
                decorator = self._color_func(frame)
            return "%s %s" % (decorator, text)

        elif icon_color and icon:
            decorator = icon_color(icon)
            return "%s %s" % (decorator, text)

        else:
            return text

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
            pointed_color = self.POINTER_COLORS.get(
                self._current_indent, self.DEFAULT_POINTED_ICON_COLOR)
            # >_✔_User_Directory_Already_Exists
            pointer = pointed_color("> ")
            return "%s%s" % (indentation, pointer)
        return ""

    def _index(self):
        if self._numbered:
            index = self._index_counter[self._current_indent] + 1
            self._index_counter[self._current_indent] += 1
            index_string = "[%s] " % index
            return constants.Colors.GRAY(index_string)
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

    def _freeze(self, failure=False, success=False):

        text = self._compose_out(failure=failure, success=success)

        # Should be stopped here, otherwise prints after
        # self._freeze call will mess up the spinner
        with self._stdout_lock:
            self.stop()
            sys.stdout.write(text)
            self._show_cursor()

            # Add Break After Spinner by Not Going Down lines - 1
            self._move_down(self._lines + 1)


class MockYaspin(CustomYaspin):
    """
    Threadless Yaspin

    Used in conjunction with the --nospin flag to make the output synchronous
    and just simple sys.stdout.write() operations, so we can more easily drop
    in and debug.
    """

    def start(self):
        self._current_line += 1
        self._lines += 1
        self._spin()
        self.indent()

    def write(self, text, indent=False, failure=False, success=False):
        """
        Write text in the terminal without breaking the spinner.
        """
        self._lines += 1
        if indent:
            self.indent()

        message = self._compose_out(
            text=text,
            failure=failure,
            success=success,
            pointed=True
        )

        with self._stdout_lock:
            self._move_down(self._lines - 1)
            sys.stdout.write(message)
            self._move_up(self._lines - 1)

    def _freeze(self, failure=False, success=False):
        text = self._compose_out(failure=failure, success=success)
        self.stop()
        sys.stdout.write(text)

    def _spin(self):
        # Compose output
        spin_phase = next(self._cycle)
        out = self._compose_out(frame=spin_phase)
        sys.stdout.write(out)

    def stop(self):
        sys.stdout.write("\r")
        self._clear_line()
