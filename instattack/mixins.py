import sys
import traceback

from instattack.config import constants
from instattack.lib.utils import break_before


class AppMixin(object):

    @break_before
    def success(self, text):
        sys.stdout.write("%s\n" % constants.LoggingLevels.SUCCESS(text))

    @break_before
    def failure(self, text, exit_code=1, tb=True):
        sys.stdout.write("%s\n" % constants.LoggingLevels.ERROR(text))

        self.exit_code = exit_code

        # We might not want to do this for all errors - argument errors or things
        # that are more expected we don't need to provide the traceback.
        if self.debug is True and tb:
            traceback.print_exc()
