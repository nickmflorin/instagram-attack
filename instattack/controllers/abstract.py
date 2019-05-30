from cement import Controller

from instattack import settings
from instattack.lib.utils import break_before


class InstattackController(Controller):

    @break_before
    def success(self, text):
        print(settings.LoggingLevels.SUCCESS(text))

    @break_before
    def failure(self, text):
        print(settings.LoggingLevels.ERROR(text))
