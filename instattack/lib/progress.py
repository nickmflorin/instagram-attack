import progressbar

from .styles import Colors


# TODO: Replace with Plumbum Progressbar
# https://plumbum.readthedocs.io/en/latest/api/cli.html
class CustomProgressbar(progressbar.ProgressBar):

    widgets = [
        ' (', progressbar.Timer(), ') ',
        progressbar.Bar(marker='#', left='|', right='|', fill=' '),
        ' (', progressbar.Counter(), ')',
        ' [', progressbar.Percentage(), '] ',
    ]

    def __init__(self, max_value, label=None):

        widgets = self.widgets[:]
        if label:
            label = f"{Colors.BLUE.format(label)}: "
            widgets.insert(0, label)

        super(CustomProgressbar, self).__init__(
            max_value=max_value,
            redirect_stdout=True,
            widgets=widgets
        )

    def update(self, value=None, force=False, **kwargs):
        value = value or self.value + 1
        # ProgressBar is finicky with last value and max_value, sometimes causes
        # index to increment by 1 over max value and throw error.  Just suppress
        # for now.
        try:
            super(CustomProgressbar, self).update(value=value, force=force, **kwargs)
        except ValueError:
            pass


class OptionalProgressbar(CustomProgressbar):

    def __init__(self, max_value, enabled=False, label=None):
        super(OptionalProgressbar, self).__init__(max_value, label=label)
        self.enabled = enabled
        if self.enabled:
            self.start()

    def update(self, value=None, force=False, **kwargs):
        if self.enabled:
            super(OptionalProgressbar, self).update(value=value, force=force, **kwargs)

    def stop(self):
        if self.enabled:
            super(OptionalProgressbar, self).stop()
