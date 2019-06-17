import curses
from curses import panel

from instattack.lib import logger
from .colors import colors
from .pairs import Pairs


class Dialog(object):

    def __init__(self, blueprint):

        self.pairs = Pairs()

        # [x] NOTE: We can also access the screen from self.blueprint.parent,
        # but this is likely going to get more complex so we will still pass in.
        self.blueprint = blueprint

        self.window = None
        self.parent = None

    def draw(self, border=False):
        self.window = self.blueprint.draw()
        self.window.refresh()
        if border:
            self.box()

    def box(self):
        self.window.attron(self.pairs[colors.black, colors.transparent])
        self.window.box()
        self.window.attroff(self.pairs[colors.black, colors.transparent])

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


class LogDialog(Dialog):

    def draw(self, border=False):
        super(MenuDialog, self).draw(border=border)

        # Enable Keypad Use - We might not want to do this for the LogDialog
        self.window.keypad(1)

        self.window.scrollok(True)
        self.window.idlok(True)
        self.window.leaveok(True)

        logger.configure_diagnostics(self.window)

        # Do We Need This Anymore?
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

    def display(self):
        """
        [x] NOTE:
        --------
        This was taken when we were using the original MenuDialog to transform
        into the LogDialog use.  We probably don't need to do this the same way
        anymore, and most likely don't need panels anymore.
        """
        self.panel.top()
        self.panel.show()

        # Will Clear Border
        self.window.clear()

        while True:
            self.window.refresh()
            curses.doupdate()
            curses.napms(400)

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()


class MenuDialog(Dialog):

    def __init__(self, blueprint, items):
        super(MenuDialog, self).__init__(blueprint)

        self.position = 0
        self.items = items
        self.items.append(('exit', 'exit'))

    def draw(self, border=False):
        super(MenuDialog, self).draw(border=border)

        # Enable Keypad Use
        self.window.keypad(1)

        # Do We Need This Anymore?
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items) - 1

    def display(self):
        self.panel.top()
        self.panel.show()
        # self.window.clear()

        while True:
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
        # self.panel.hide()
        panel.update_panels()
        curses.doupdate()
