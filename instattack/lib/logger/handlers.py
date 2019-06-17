import logging
import sys

from termx.logging import TermxHandler

from .formats import TERMX_FORMAT_STRING, SIMPLE_FORMAT_STRING


class TypeFilter(logging.Filter):
    """
    Used to use when we had simultaneous use of both simple, bar and artsy
    output.  Since we do not do that anymore, we do not need this but will
    keep the code around temporarily.
    """

    def __init__(self, require=None, disallow=None, *args, **kwargs):
        super(TypeFilter, self).__init__(*args, **kwargs)
        self.require = require
        self.disallow = disallow

    def filter(self, record):
        if self.require:
            if not all([x in record.__dict__ for x in self.require]):
                return False

        if self.disallow:
            if any([x in record.__dict__ for x in self.disallow]):
                return False
        return True


class SimpleHandler(logging.StreamHandler):

    def __init__(self, filter=None, formatter=None):
        super(SimpleHandler, self).__init__(stream=sys.stderr)

        if formatter:
            self.setFormatter(formatter)
        if filter:
            self.addFilter(filter)


class DiagnosticsHandler(SimpleHandler):
    """
    >>> https://stackoverflow.com/questions/27774093/how-to-manage-logging-in-curses

    We cannot use ArtsyLogger right now because those UNICODE formats do not
    display nicely with curses.
    """

    def __init__(self, window, filter=None, formatter=None):
        super(DiagnosticsHandler, self).__init__(filter=filter, formatter=formatter)
        self.window = window
        self.x = 1

    def add_lines(self, ufs, msg, code=None):
        lines = msg.split('\n')
        for line in lines:
            if not code:
                self.window.addstr((ufs % line))
            else:
                self.window.addstr((ufs % line).encode(code))
        self.window.refresh()

    def emit(self, record):
        """
        window = self.panel.window()
        for i, line in enumerate(lines):
            y, x = window.getyx()
            window.move(y + 1, 1)
            window.addstr(1, 1, "%s\r" % line)
            window.refresh()
        """
        try:
            msg = self.format(record)
            fs = "\n%s"
            try:
                self.add_lines(fs, msg, code=None)
            except UnicodeError:
                self.add_lines(fs, msg, code='UTF-8')
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


SIMPLE_HANDLERS = [
    SimpleHandler(formatter=SIMPLE_FORMAT_STRING),
]


TERMX_HANDLERS = [
    TermxHandler(
        handler_cls=logging.StreamHandler,
        format_string=TERMX_FORMAT_STRING
    ),
]
