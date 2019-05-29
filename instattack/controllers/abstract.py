from cement import Controller

from instattack.app import settings


class InstattackController(Controller):

    def success(self, text):
        print(settings.LoggingLevels.SUCCESS(text))
