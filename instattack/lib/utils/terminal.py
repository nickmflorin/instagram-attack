import re
import sys


def escape_ansi_string(value):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', value)


def measure_ansi_string(value):
    bare = escape_ansi_string(value)
    return len(bare)


class cursor:

    @classmethod
    def newline():
        sys.stdout.write("\n")

    @classmethod
    def move_right(n=1):
        chars = "\u001b[%sC" % n
        sys.stdout.write(chars)

    @classmethod
    def move_left(n=1):
        chars = "\u001b[%sD" % n
        sys.stdout.write(chars)

    @classmethod
    def move_up(n=1):
        chars = "\u001b[%sA" % n
        sys.stdout.write(chars)

    @classmethod
    def move_down(n=1):
        chars = "\u001b[%sB" % n
        sys.stdout.write(chars)

    @classmethod
    def show_cursor():
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    @classmethod
    def hide_cursor():
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
