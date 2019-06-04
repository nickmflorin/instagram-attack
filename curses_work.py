import curses
import logging
import time


class CursesHandler(logging.Handler):

    def __init__(self, window):
        logging.Handler.__init__(self)
        self.window = window
        self.x = 1

    def emit(self, record):
        try:
            msg = self.format(record)

            fs = "%s\r"
            self.window.addstr(fs % msg)
            self.window.refresh()

            y, x = self.window.getyx()
            self.window.move(y + 1, self.x)

        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


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


def draw_panelA():
    pass


def draw_panels(stdscr):
    k = 0

    # Clear and refresh the screen for a blank canvas
    while (k != ord('q')):
        stdscr.clear()
        stdscr.refresh()

        curses.echo()
        curses.start_color()
        curses.use_default_colors()

        p = ApplicationPanel(stdscr)
        p2 = StatsPanel(stdscr)
        l1 = LogPanel1(stdscr)
        l2 = LogPanel2(stdscr)

        mh = CursesHandler(p.window)

        formatterDisplay = logging.Formatter(
            '%(asctime)-8s|%(name)-12s|%(levelname)-6s|%(message)-s', '%H:%M:%S')
        mh.setFormatter(formatterDisplay)
        logger = logging.getLogger('myLog')
        logger.addHandler(mh)

        p.window.move(4, 1)
        for i in range(10):
            logger.error('message ' + str(i))
            time.sleep(1)

        # curses.curs_set(1)
        # curses.nocbreak()
        # curses.echo()
        # curses.endwin()
        # win.scrollok(True)
        # win.idlok(True)
        # win.leaveok(True)

        # Refresh the screen
        stdscr.refresh()

        k = stdscr.getch()


def draw_menu(stdscr):
    k = 0
    cursor_x = 0
    cursor_y = 0

    # Clear and refresh the screen for a blank canvas
    stdscr.clear()
    stdscr.refresh()

    # Start colors in curses
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

    # Loop where k is the last character pressed
    while (k != ord('q')):

        # Initialization
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        if k == curses.KEY_DOWN:
            cursor_y = cursor_y + 1
        elif k == curses.KEY_UP:
            cursor_y = cursor_y - 1
        elif k == curses.KEY_RIGHT:
            cursor_x = cursor_x + 1
        elif k == curses.KEY_LEFT:
            cursor_x = cursor_x - 1

        cursor_x = max(0, cursor_x)
        cursor_x = min(width-1, cursor_x)

        cursor_y = max(0, cursor_y)
        cursor_y = min(height-1, cursor_y)

        # Declaration of strings
        title = "Curses example"[:width-1]
        subtitle = "Written by Clay McLeod"[:width-1]
        keystr = "Last key pressed: {}".format(k)[:width-1]
        statusbarstr = "Press 'q' to exit | STATUS BAR | Pos: {}, {}".format(cursor_x, cursor_y)
        if k == 0:
            keystr = "No key press detected..."[:width-1]

        # Centering calculations
        start_x_title = int((width // 2) - (len(title) // 2) - len(title) % 2)
        start_x_subtitle = int((width // 2) - (len(subtitle) // 2) - len(subtitle) % 2)
        start_x_keystr = int((width // 2) - (len(keystr) // 2) - len(keystr) % 2)
        start_y = int((height // 2) - 2)

        # Rendering some text
        whstr = "Width: {}, Height: {}".format(width, height)
        stdscr.addstr(0, 0, whstr, curses.color_pair(1))

        # Render status bar
        stdscr.attron(curses.color_pair(3))
        stdscr.addstr(height-1, 0, statusbarstr)
        stdscr.addstr(height-1, len(statusbarstr), " " * (width - len(statusbarstr) - 1))
        stdscr.attroff(curses.color_pair(3))

        # Turning on attributes for title
        stdscr.attron(curses.color_pair(2))
        stdscr.attron(curses.A_BOLD)

        # Rendering title
        stdscr.addstr(start_y, start_x_title, title)

        # Turning off attributes for title
        stdscr.attroff(curses.color_pair(2))
        stdscr.attroff(curses.A_BOLD)

        # Print rest of text
        stdscr.addstr(start_y + 1, start_x_subtitle, subtitle)
        stdscr.addstr(start_y + 3, (width // 2) - 2, '-' * 4)
        stdscr.addstr(start_y + 5, start_x_keystr, keystr)
        stdscr.move(cursor_y, cursor_x)

        # Refresh the screen
        stdscr.refresh()

        # Wait for next input
        k = stdscr.getch()

def main():
    # stdscr = curses.initscr()
    # stdscr.clear()
    curses.wrapper(draw_panels)

if __name__ == '__main__':
    main()
