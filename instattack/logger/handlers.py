import logging

from .log_formats import (
    LOG_FORMAT_STRING, BARE_FORMAT_STRING, SIMPLE_FORMAT_STRING,
    EXTERNAL_FORMAT_STRING)


class TypeFilter(logging.Filter):

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


class CustomFormatter(logging.Formatter):

    def __init__(self, format_string=LOG_FORMAT_STRING, **kwargs):
        super(CustomFormatter, self).__init__(**kwargs)
        self.format_string = format_string

    def format(self, record):
        format_string = self.format_string(record)
        return format_string.format(record)


class CustomHandler(logging.StreamHandler):

    def __init__(self, filter=None, format_string=LOG_FORMAT_STRING):
        super(CustomHandler, self).__init__()

        formatter = CustomFormatter(format_string=format_string)
        self.setFormatter(formatter)

        if filter:
            self.addFilter(filter)


class ExternalFormatter(logging.Formatter):

    def format(self, record):
        format_string = EXTERNAL_FORMAT_STRING(record)
        return format_string.format(record)


class ExternalHandler(logging.StreamHandler):

    def __init__(self):
        super(ExternalHandler, self).__init__()
        self.setFormatter(ExternalFormatter())


BARE_HANDLER = CustomHandler(
    format_string=BARE_FORMAT_STRING,
    filter=TypeFilter(require=['bare']),
)

SIMPLE_HANDLER = CustomHandler(
    format_string=SIMPLE_FORMAT_STRING,
    filter=TypeFilter(require=['simple']),
)

BASE_HANDLER = CustomHandler(
    format_string=LOG_FORMAT_STRING,
    filter=TypeFilter(disallow=['bare', 'simple'])
)
