import curses
import threading
from blinker import signal

from .colors import colors
from .pairs import Pairs
from .blueprint import BluePrint
from .dialogs import AnalyticsDialog, LogDialog, DebugLogDialog


diagnostics = signal('diagnostics')


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

global screen


class Diagnostics(object):

    def __init__(self, stdscreen, on_exit, stop_event):

        self.pairs = Pairs()
        self.blueprints = {}

        self.exit = on_exit
        self.stop_event = stop_event

        # Here, w is a ratio of the leftover space, but we want to eventually
        # allow to specify leftover space OR total horizontal space.
        self.blueprints['analytics'] = BluePrint(w=0.5, h=0.5, parent=screen, x=1, y=1)
        self.blueprints['logging'] = BluePrint(w=0.5, h=0.5, parent=screen, x=self.blueprints['analytics'].x2 + 1, y=1)
        self.blueprints['debug'] = BluePrint(w=1.0, h=0.5, parent=screen, x=1, y=self.blueprints['logging'].y2 + 1)

        self.dialogs = {
            'analytics': AnalyticsDialog(
                blueprint=self.blueprints['analytics'],
                on_exit=self.exit,
                stop_event=self.stop_event,
                border=self.pairs[colors.black, colors.transparent]
            ),
            'logging': LogDialog(
                blueprint=self.blueprints['logging'],
                on_exit=self.exit,
                stop_event=self.stop_event,
                border=self.pairs[colors.black, colors.transparent]
            ),
            'debug': DebugLogDialog(
                blueprint=self.blueprints['debug'],
                on_exit=self.exit,
                stop_event=self.stop_event,
                border=self.pairs[colors.black, colors.transparent]
            )
        }

    def draw(self):
        self.dialogs['analytics'].draw()
        self.dialogs['logging'].draw()
        self.dialogs['debug'].draw()

        global screen
        screen.refresh()

    def dispatch(self, event):
        dialog = event.get('dialog')
        if not dialog:
            self.exit()
            raise RuntimeError('Dialog Must be Provided')
        self.dialogs[dialog].dispatch(event)

    def start(self):
        thread = threading.Thread(target=self.dialogs['logging'].start)
        thread.start()
        thread.join()


def prepare_curses():

    # Initialize Global Screen Object
    global screen
    screen = curses.initscr()

    # Disable Keypress Echo to Prevent Double Input
    curses.noecho()

    # Disable Line Buffers to Run Keypress Immediately
    curses.cbreak()
    screen.keypad(True)

    curses.start_color()
    curses.use_default_colors()


def end_curses(stop_event):

    def _end_curses():
        global screen

        if screen is None:
            raise RuntimeError('Screen not initialized.')

        # End Curses Style Terminal
        curses.nocbreak()
        screen.keypad(False)
        curses.echo()

        # Restores Terminal to Normal Operating Mode
        curses.endwin()
    return _end_curses


def run_diagnostics():

    prepare_curses()

    stop_event = threading.Event()

    d = Diagnostics(screen, stop_event=stop_event, on_exit=end_curses(stop_event))
    diagnostics.connect(d.dispatch)

    d.draw()
    d.start()
