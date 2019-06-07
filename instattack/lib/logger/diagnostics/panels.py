import curses


class Panel:

    def __init__(self, stdscr):
        sheight, swidth = stdscr.getmaxyx()

        self.width = int(swidth * self._width)
        self.height = int(sheight * self._height)
        self.y = int(sheight * self._y)
        self.x = int(swidth * self._x)

        self.window = curses.newwin(self.height, self.width, self.y, self.x)
        self.window.border()

        self.window.addstr(1, 1, self.header)
        self.window.refresh()


class ApplicationPanel(Panel):

    _x = 0
    _y = 0
    _width = 0.6
    _height = 0.3
    header = "Instattack"


class StatsPanel(Panel):

    _x = 0.6
    _y = 0
    _width = 0.4
    _height = 0.3
    header = "Stats"


class LogPanel1(Panel):

    _x = 0.0
    _y = 0.3
    _width = 0.4
    _height = 0.3
    header = "Stats"


class LogPanel2(Panel):

    _x = 0.0
    _y = 0.6
    _width = 0.4
    _height = 0.3
    header = "Stats"
