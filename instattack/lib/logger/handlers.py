import logging
import sys

from artsylogger import ArtsyHandlerMixin

from instattack.config import constants
from instattack.lib.utils import relative_to_root

from .formats import LOG_FORMAT_STRING, SIMPLE_FORMAT_STRING


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


class DiagnosticsHandler(ArtsyHandler):

    def __init__(self, window):
        logging.Handler.__init__(self)
        self.window = window
        self.x = 1

    def emit(self, record):
        try:
            msg = self.format(record)

            fs = "%s\r"
            self.window.addstr(fs % msg)
            self.window.refresh()

            y, x = self.window.getyx()
            self.window.move(y + 1, self.x)

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


SIMPLE_HANDLERS = [
    SimpleHandler(formatter=SIMPLE_FORMAT_STRING),
]


ARTSY_HANDLERS = [
    ArtsyHandler(format_string=LOG_FORMAT_STRING),
]
