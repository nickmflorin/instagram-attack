import sys


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
