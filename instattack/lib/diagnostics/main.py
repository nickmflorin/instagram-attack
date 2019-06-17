import curses

from .colors import colors
from .pairs import Pairs
from .blueprint import BluePrint
from .dialogs import MenuDialog, LogDialog


"""
[x] NOTES
---------


[x] Useful Modules
------------------

- Curses ASCII
    https://docs.python.org/3.3/library/curses.ascii.html#module-curses.ascii
- Curse Box
    https://github.com/Tenchi2xh/cursebox

[x] Resources
-------------
- Curses Module Functions
    https://docs.python.org/3.3/library/curses.html#curses.endwin
"""


class Diagnostics(object):
    """
    A good example of creating a curses menu.  Potentially useful in the
    future.
    """

    def __init__(self, stdscreen):
        self.general_setup()
        self.screen = stdscreen

        self.pairs = Pairs()

        self.screen.attron(self.pairs[colors.black, colors.transparent])
        self.screen.box()
        self.screen.attroff(self.pairs[colors.black, colors.transparent])

        blueprint1 = BluePrint(w=0.5, h=0.5, parent=self.screen, x=1, y=1)
        # Here, w is a ratio of the leftover space, but we want to eventually
        # allow to specify leftover space OR total horizontal space.
        blueprint2 = blueprint1.duplicate_right(padding=1, w=1.0)
        self.blueprints = [blueprint1, blueprint2]

        self.start_log()
        self.start_menu()
        self.screen.refresh()

    def start_log(self):

        window = LogDialog(self.blueprints[1], self.screen)
        window.draw(border=True)
        window.refresh()

    def start_menu(self):
        # submenu_items = [
        #     ('beep', curses.beep),
        #     ('flash', curses.flash)
        # ]
        main_menu_items = [
            ('beep', curses.beep),
            ('flash', curses.flash),
            # ('submenu', submenu.display)
        ]

        main_menu = MenuDialog(self.blueprints[0], self.screen, main_menu_items)
        main_menu.draw(border=True)
        main_menu.display()

    @staticmethod
    def general_setup():
        # Disable Keypress Echo to Prevent Double Input
        curses.noecho()

        # Disable Line Buffers to Run Keypress Immediately
        curses.cbreak()
        curses.start_color()
        curses.use_default_colors()

        # Restores Terminal to Normal Operating Mode
        # curses.endwin()


def run_diagnostics():
    curses.wrapper(Diagnostics)
