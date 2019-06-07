import re
import sys


def escape_ansi_string(value):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', value)


def measure_ansi_string(value):
    bare = escape_ansi_string(value)
    return len(bare)


class cursor:

    @staticmethod
    def _move_up():
        sys.stdout.write("\033[F")

    @staticmethod
    def _move_down():
        sys.stdout.write("\n")

    @staticmethod
    def move_up(nlines=1):
        for i in range(nlines):
            cursor._move_up()

    @staticmethod
    def move_down(nlines=1):
        for i in range(nlines):
            cursor._move_down()

    @staticmethod
    def show_cursor():
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @staticmethod
    def hide_cursor():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
