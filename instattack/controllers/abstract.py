import asyncio
from cement import Controller

from instattack.config import settings
from instattack.lib.utils import break_before


class InstattackController(Controller):

    @break_before
    def success(self, text):
        print(settings.LoggingLevels.SUCCESS(text))

    @break_before
    def failure(self, text):
        print(settings.LoggingLevels.ERROR(text))

    def _dispatch(self, *args, **kwargs):
        self.loop = asyncio.get_event_loop()
        setattr(self.loop, 'config', self.app.config)
        super(InstattackController, self)._dispatch(*args, **kwargs)
