from platform import python_version
from plumbum import cli
import sys

from instattack.lib import LoggableMixin, validate_log_level


class BaseApplication(cli.Application, LoggableMixin):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.

    TODO
    ----
    .cleanup()
    Method performed in cli.Application after all components of main() have
    completed.
    """

    # Even though we are not using the log level internally, and setting
    # it in __main__, we still have to allow this to be a switch otherwise
    # CLI will complain about unknown switch.
    level = cli.SwitchAttr("--level", validate_log_level, default='INFO')


class Instattack(BaseApplication):

    def main(self, *args):
        self.validate(*args)

    def validate(self, *args):
        if int(python_version()[0]) < 3:
            self.log.error('Please use Python 3')
            sys.exit()
        if args:
            self.log.error("Unknown command %r" % (args[0]))
            sys.exit()
        # The nested command will be`None if no sub-command follows
        if not self.nested_command:
            self.log.error("No command given")
            sys.exit()
