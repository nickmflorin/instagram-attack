import asyncio
from cement import Controller, shell

from termx import settings as termx, Cursor

from instattack.lib import logger


class PrintableMixin(object):

    def success(self, text):
        Cursor.write(termx.Formats.SUCCESS(text))

    def failure(self, text):
        Cursor.write(termx.Formats.FAIL(text))

    def breakline(self):
        Cursor.newline()


class InstattackController(Controller, PrintableMixin):

    def _post_argument_parsing(self):
        if self.app.pargs.level is not None:
            logger.setLevel(self.app.pargs.level)

    def proceed(self, message):

        fmt = termx.Formats.TEXT.NORMAL.with_style('bold')
        message = fmt(f"{message}") + ", (Press Enter to Continue)"

        p = shell.Prompt("%s" % message, default="ENTER")
        res = p.prompt()

        self.breakline()

        if res == 'ENTER':
            return True
        return False

    def _dispatch(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        setattr(self, 'loop', loop)
        super(InstattackController, self)._dispatch(*args, **kwargs)
