import curses
from curses import panel
import threading

from instattack.lib import logger

from .pairs import Pairs


class Dialog(object):

    window = None
    parent = None

    def __init__(self, blueprint, on_exit, stop_event, border=None):
        """
        [x] NOTE:
        ---------
        We can also access the screen from self.blueprint.parent, but this is
        likely going to get more complex so we will still pass in.
        """
        self.pairs = Pairs()

        self.blueprint = blueprint
        self.border = border
        self.exit = on_exit

        self.stop_event = stop_event

    def draw(self):
        self.window = self.blueprint.draw()
        self.outline()
        self.label()
        self.window.refresh()

    def outline(self):
        if self.border:
            self.window.attron(self.border)
            self.window.box()
            self.window.attroff(self.border)

    def __getattr__(self, name):
        if hasattr(self.window, name):
            return getattr(self.window, name)
        raise AttributeError('Invalid Attribute %s.' % name)

    @classmethod
    def split_horizontally(cls, screen, y=1):
        pass

    @property
    def coordinates(self):
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def dimensions(self):
        return (self.height, self.width)

    @property
    def width(self):
        h, w = self.parent.getmaxyx()
        available_width = int(w - 2.0 * self.x)
        return int(self.xratio * available_width)

    @property
    def height(self):
        h, w = self.parent.getmaxyx()
        available_height = int(h - 2.0 * self.y)
        return int(self.yratio * available_height)

    def label(self):
        self.window.addstr(2, 2, self.__LABEL__)


class LogDialog(Dialog):

    __LABEL__ = "Logging"

    def draw(self):
        super(LogDialog, self).draw()

        # Note: Not Enabling Keypad Yet
        self.window.scrollok(True)
        self.window.idlok(True)
        self.window.leaveok(True)

        logger.configure_diagnostics(self.window)

    def dispatch(self, event):
        data = event.get('data')
        self.window.addstr(5, 5, data)

        self.stop_event.set()
        self.exit()

    def start(self):
        """
        [x] NOTE:
        --------
        This was taken when we were using the original MenuDialog to transform
        into the LogDialog use.  We probably don't need to do this the same way
        anymore, and most likely don't need panels anymore.
        """
        # self.panel.top()
        # self.panel.show()
        count = 0
        while not self.stop_event.is_set():
            if self.stop_event.is_set():
                self.window.addstr('Stopping')
            elif count == 100:
                break
            else:
                self.window.addstr(count + 5, 5, "TEST")
                curses.napms(400)
                self.window.refresh()
                count += 1


class DebugLogDialog(LogDialog):

    __LABEL__ = "Debug Logging"

    def draw(self):
        super(DebugLogDialog, self).draw()

        # Note: Not Enabling Keypad Yet
        self.window.scrollok(True)
        self.window.idlok(True)
        self.window.leaveok(True)

        logger.configure_diagnostics(self.window)

    def dispatch(self, event):
        data = event.get('data')
        self.window.addstr(5, 5, data)

        self.stop_event.set()
        self.exit()

    def start(self):
        """
        [x] NOTE:
        --------
        This was taken when we were using the original MenuDialog to transform
        into the LogDialog use.  We probably don't need to do this the same way
        anymore, and most likely don't need panels anymore.
        """
        # self.panel.top()
        # self.panel.show()
        count = 0
        while not self.stop_event.is_set():
            if self.stop_event.is_set():
                self.window.addstr('Stopping')
            elif count == 100:
                break
            else:
                self.window.addstr(count + 5, 5, "TEST")
                curses.napms(400)
                self.window.refresh()
                count += 1


class AnalyticsDialog(Dialog):

    __LABEL__ = "Analytics"

    main_menu_items = [
        ('beep', curses.beep),
        ('flash', curses.flash),
        # ('submenu', submenu.display)
    ]

    def __init__(self, blueprint, on_exit, stop_event, border=None):
        super(AnalyticsDialog, self).__init__(blueprint, on_exit, stop_event, border=border)

        self.position = 0
        self.items = self.main_menu_items[:]
        self.items.append(('exit', 'exit'))

    def draw(self):
        super(AnalyticsDialog, self).draw()

        # Enable Keypad Use
        self.window.keypad(1)

        # Do We Need This Anymore?
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

    def dispatch(self, event):
        data = event.get('data')
        self.window.addstr(5, 5, data)

    def notify(self, event):
        self.window.addstr(5, 5, event)

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items) - 1

    def start(self):
        self.panel.top()
        self.panel.show()
        # self.window.clear()

        while not self.stop_event.is_set():
            self.window.refresh()
            curses.doupdate()
            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL

                msg = '%d. %s' % (index, item[0])
                self.window.addstr(1 + index, 1, msg, mode)

            key = self.window.getch()

            if key in [curses.KEY_ENTER, ord('\n')]:
                if self.position == len(self.items) - 1:
                    break
                else:
                    self.items[self.position][1]()

            elif key == curses.KEY_UP:
                self.navigate(-1)

            elif key == curses.KEY_DOWN:
                self.navigate(1)

        # self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()
        self.exit()
