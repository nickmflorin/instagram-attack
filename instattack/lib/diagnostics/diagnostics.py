import curses
from curses import panel

from instattack.lib import logger


class LogDisplay(object):

    def __init__(self, screen):
        self.window = screen.subwin(0, 0)
        # self.window.border()
        self.window.keypad(1)

        self.window.scrollok(True)
        self.window.idlok(True)
        self.window.leaveok(True)

        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

        logger.configure_diagnostics(self.window)

    def display(self):
        self.panel.top()
        self.panel.show()
        # self.panel.border()

        self.window.clear()

        while True:
            self.window.refresh()
            curses.doupdate()
            curses.napms(400)

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()


class Diagnostics(object):

    def __init__(self, stdscreen):
        self.screen = stdscreen
        curses.curs_set(0)

        log_display = LogDisplay(self.screen)
        log_display.display()

        # main_menu = Menu(main_menu_items, self.screen)
        # main_menu.display()


async def run_diagnostics():
    curses.wrapper(Diagnostics)


"""
Curses examples below for reference.
"""


class Menu(object):
    """
    A good example of creating a curses menu.  Potentially useful in the
    future.
    """

    def __init__(self, items, stdscreen):
        self.window = stdscreen.subwin(0, 0)
        self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()

        self.position = 0
        self.items = items
        self.items.append(('exit', 'exit'))

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items) - 1

    def display(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()

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

        self.window.clear()
        self.panel.hide()
        panel.update_panels()
        curses.doupdate()


class MenuApp(object):
    """
    A good example of creating a curses menu.  Potentially useful in the
    future.
    """

    def __init__(self, stdscreen):

        submenu_items = [
            ('beep', curses.beep),
            ('flash', curses.flash)
        ]
        submenu = Menu(submenu_items, self.screen)

        main_menu_items = [
            ('beep', curses.beep),
            ('flash', curses.flash),
            ('submenu', submenu.display)
        ]
        main_menu = Menu(main_menu_items, self.screen)
        main_menu.display()


class RedirectOutput:

    def __init__(self, stdout, window):
        self.stdout = stdout
        self.window = window
        self.current_line = 1

        import builtins
        builtins.input = self.prompt

    def flush(self):
        pass

    def isatty(self):
        return False

    def write(self, s):
        self.stdout.write(s)
        # self.window.addstr(self.current_line, 1, "%s" % s)
        self.window.refresh()
        self.current_line += 1
        # self.window.addstr(1, 1, "%s" % s)
