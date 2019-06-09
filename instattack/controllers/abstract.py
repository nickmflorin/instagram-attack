import asyncio
from cement import Controller, shell
import sys

from instattack.lib import logger
from instattack.config import constants


class PrintableMixin(object):

    def success(self, text):
        sys.stdout.write("%s\n" % constants.Formats.State.SUCCESS(text))

    def failure(self, text):
        sys.stdout.write("%s\n" % constants.Formats.State.FAIL(text))

    def breakline(self):
        sys.stdout.write("\n")


class InstattackController(Controller, PrintableMixin):

    def _post_argument_parsing(self):
        if self.app.pargs.level is not None:
            logger.setLevel(self.app.pargs.level)

    def proceed(self, message):

        fmt = constants.Formats.Text.NORMAL.with_bold()
        message = fmt(f"{message}") + ", (Press Enter to Continue)"

        p = shell.Prompt(message, default="ENTER")
        res = p.prompt()
        self.breakline()

        if res == 'ENTER':
            return True
        return False

    def _dispatch(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        setattr(self, 'loop', loop)
        super(InstattackController, self)._dispatch(*args, **kwargs)
