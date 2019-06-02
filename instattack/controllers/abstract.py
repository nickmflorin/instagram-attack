import asyncio
from cement import Controller
import sys

from instattack.config import settings


class PrintableMixin(object):

    def success(self, text):
        sys.stdout.write("%s\n" % settings.LoggingLevels.SUCCESS(text))

    def failure(self, text):
        sys.stdout.write("%s\n" % settings.LoggingLevels.ERROR(text))


class InstattackController(Controller, PrintableMixin):

    def _dispatch(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        setattr(self, 'loop', loop)
        super(InstattackController, self)._dispatch(*args, **kwargs)
