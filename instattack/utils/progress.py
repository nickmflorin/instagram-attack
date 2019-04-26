from __future__ import absolute_import

import progressbar

from instattack.conf import Colors


# TODO: Replace with Plumbum Progressbar
# https://plumbum.readthedocs.io/en/latest/api/cli.html
class CustomProgressbar(progressbar.ProgressBar):

    def update(self, value=None, force=False, **kwargs):
        value = value or self.value + 1
        # ProgressBar is finicky with last value and max_value, sometimes causes
        # index to increment by 1 over max value and throw error.  Just suppress
        # for now.
        try:
            super(CustomProgressbar, self).update(value=value, force=force, **kwargs)
        except ValueError:
            pass


widgets = [
    ' (', progressbar.Timer(), ') ',
    progressbar.Bar(marker='#', left='|', right='|', fill=' '),
    ' (', progressbar.Counter(), ')',
    ' [', progressbar.Percentage(), '] ',
]


def bar(label=None, max_value=None):
    if label:
        label = f"{Colors.BLUE.format(label)}: "
        widgets.insert(0, label)

    return CustomProgressbar(
        max_value=max_value,
        redirect_stdout=True,
        widgets=widgets
    )
