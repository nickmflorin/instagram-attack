import logging
from plumbum import colors


__all__ = ('ArtsyHandlerMixin', 'ArtsyFormatter', )


class ArtsyFormatter(logging.Formatter):

    def __init__(self, format_string=None, **kwargs):
        super(ArtsyFormatter, self).__init__(**kwargs)
        self.format_string = format_string

    def format(self, record):
        format_string = self.format_string(record)
        return format_string.format(record)


class ArtsyHandlerMixin(object):

    formatter_cls = ArtsyFormatter

    def default(self, record, attr, default=None):
        setattr(record, attr, getattr(record, attr, default))

    def prepare_record(self, record):
        self.default(record, 'line_index')
        self.default(record, 'color')

        if record.color:
            if isinstance(record.color, str):
                setattr(record, 'color', colors.fg(record.color))

    def useArtsyFormatter(self, format_string=None):
        formatter = self.formatter_cls(format_string=format_string)
        self.setFormatter(formatter)

    def emit(self, record):
        self.prepare_record(record)
        super(ArtsyHandlerMixin, self).emit(record)
