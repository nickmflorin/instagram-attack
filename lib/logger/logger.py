import contextlib
import logbook
import progressbar
import traceback
import sys

from .formatter import (
    record_formatter, LOG_FORMAT_STRING, SIMPLE_FORMAT_STRING, BARE_FORMAT_STRING)


__all__ = ('AppLogger', 'log_handling', )


class CustomStreamHandler(logbook.StreamHandler):

    def __init__(self, level='INFO', format_string=LOG_FORMAT_STRING, filter=None):
        super(CustomStreamHandler, self).__init__(
            sys.stdout,
            level=level,
            filter=filter,
            bubble=True
        )
        self.formatter = record_formatter(format_string=format_string)


class AppLogger(logbook.Logger):

    def simple(self, message, color=None, extra=None):
        # Level shouldn't really matter, since we aren't outputting it anyways and
        # are just going to choose an output in this method.
        extra = extra or {}
        extra.update(color=color, simple=True)
        self.info(message, extra=extra)

    def bare(self, message, color='darkgray'):
        self.info(message, extra={'bare': True, 'color': color})

    def line_by_line(self, lines, color='darkgray', numbered=True):
        """
        TODO
        ----
        Move the numeric indexing to the formatter, by specifing line_index
        or some other type of context.
        """
        for i in range(len(lines)):
            item = lines[i]
            if numbered:
                item = f"[{i + 1}] {lines[i]}"
            self.bare(item, color=color)

    def traceback(self, ex, ex_traceback=None, raw=False):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        if ex_traceback is None:
            ex_traceback = ex.__traceback__

        tb_lines = [
            line.rstrip('\n') for line in
            traceback.format_exception(ex.__class__, ex, ex_traceback)
        ]

        # This can be used if we want to just output the raw error.
        if raw:
            for line in tb_lines:
                sys.stderr.write("%s\n" % line)
        else:
            self.error("\n".join(tb_lines), extra={'no_indent': True})


class log_handling(object):

    def __init__(self, level):
        self.level = level

    def __call__(self, f):

        def wrapped(instance, *args, **kwargs):
            if self.level == 'self':
                self.level = getattr(instance, 'level')

            with self.context():
                return f(instance, *args, **kwargs)
        return wrapped

    @contextlib.contextmanager
    def context(self):

        bare_handler = CustomStreamHandler(
            level='INFO',
            format_string=BARE_FORMAT_STRING,
            filter=lambda r, h: ('bare' in r.extra and
                all([x not in r.extra for x in ('simple', )]))
        )

        simple_handler = CustomStreamHandler(
            level='INFO',
            format_string=SIMPLE_FORMAT_STRING,
            filter=lambda r, h: ('simple' in r.extra and
                all([x not in r.extra for x in ('bare', )]))
        )

        base_handler = CustomStreamHandler(
            level=self.level,
            format_string=LOG_FORMAT_STRING,
            filter=lambda r, h: ('simple' in r.extra and
                all([x not in r.extra for x in ('bare', 'simple', )]))
        )

        self._init_progressbar()
        try:
            with base_handler, simple_handler, bare_handler:
                yield
        finally:
            self._deinit_progressbar()

    def _init_progressbar(self):
        progressbar.streams.wrap_stderr()
        progressbar.streams.wrap_stdout()

    def _deinit_progressbar(self):
        progressbar.streams.unwrap_stdout()
        progressbar.streams.unwrap_stderr()
