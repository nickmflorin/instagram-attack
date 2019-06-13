import logging
import sys

from artsylogger import ArtsyHandlerMixin

from instattack.config import constants
from instattack.lib.utils import relative_to_root

from .formats import LOG_FORMAT_STRING, SIMPLE_FORMAT_STRING

# I don't think this is necessary for Python3 but we will leave now anyways,
# for purposes of consistency with the example.
try:
    unicode
    _unicode = True
except NameError:
    _unicode = False


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


class CustomHandlerMixin(ArtsyHandlerMixin):

    def prepare_record(self, record):
        super(CustomHandlerMixin, self).prepare_record(record)

        if not getattr(record, 'level', None):
            setattr(record, 'level', constants.LoggingLevels[record.levelname])

        record.pathname = relative_to_root(record.pathname)


class SimpleHandler(logging.StreamHandler):

    def __init__(self, filter=None, formatter=None):
        super(SimpleHandler, self).__init__(stream=sys.stderr)

        if formatter:
            self.setFormatter(formatter)
        if filter:
            self.addFilter(filter)


class ArtsyHandler(SimpleHandler, CustomHandlerMixin):

    def __init__(self, filter=None, format_string=None):
        super(ArtsyHandler, self).__init__(filter=filter)
        self.useArtsyFormatter(format_string=format_string)

    def emit(self, record):
        self.prepare_record(record)
        super(ArtsyHandler, self).emit(record)


class DiagnosticsHandler(SimpleHandler):
    """
    >>> https://stackoverflow.com/questions/27774093/how-to-manage-logging-in-curses

    We cannot use ArtsyLogger right now because those UNICODE formats do not
    display nicely with curses.
    """

    def __init__(self, window, filter=None, formatter=None):
        SimpleHandler.__init__(self, filter=filter, formatter=formatter)
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
            if not _unicode:  # if no unicode support...
                self.add_lines(fs, msg, code=None)
            else:
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


ARTSY_HANDLERS = [
    ArtsyHandler(format_string=LOG_FORMAT_STRING),
]
