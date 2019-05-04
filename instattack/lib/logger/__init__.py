import logbook

from .handlers import log_handling  # noqa


class AppLogger(logbook.Logger):

    def handle_global_exception(self, exc):
        """
        Can only handle instances of traceback.TracebackException.
        Might want to look into asyncio utilities on loop for handling exceptions.
        """
        tb = exc.exc_traceback

        log = tb.tb_frame.f_globals.get('log')
        if not log:
            log = tb.tb_frame.f_locals.get('log')

        # Array of lines for the stack trace - might be useful later.
        # trace = traceback.format_exception(ex_type, ex, tb, limit=3)
        self.exception(exc, extra={
            'lineno': exc.stack[-1].lineno,
            'filename': exc.stack[-1].filename,
        })

    # @contextlib.contextmanager
    # def start_and_done(self, action_string, level='WARNING', exit_level='DEBUG'):
    #     methods = {
    #         'INFO': self.info,
    #         'NOTICE': self.notice,
    #         'DEBUG': self.debug,
    #         'WARNING': self.warning,
    #     }
    #     method = methods[level.upper()]
    #     exit_method = methods[exit_level.upper()]

    #     # This doesn't seem to be working...
    #     stacks = traceback.extract_stack()
    #     stacks = [
    #         st for st in stacks if (all([
    #             not st.filename.startswith('/Library/Frameworks/'),
    #             not any([x in st.filename for x in ['stdin', 'stderr', 'stdout']]),
    #             __file__ not in st.filename,
    #         ]))
    #     ]

    #     try:
    #         method(f'{action_string}...', extra={
    #             'lineno': stacks[-1].lineno,
    #             'filename': stacks[-1].filename,
    #         })
    #         yield
    #     finally:
    #         exit_method(f'Done {action_string}.', extra={
    #             'lineno': stacks[-1].lineno,
    #             'filename': stacks[-1].filename,
    #         })
