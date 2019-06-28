"""
[x] NOTE:
--------
We want to keep these constants separate from __init__.py, since we want to be
able to load config.settings in __init__.py, and these constants are used by
config.settings.
"""

__NAME__ = 'instattack'
__FORMAL_NAME__ = __NAME__.title()
__VERSION__ = (0, 0, 1, 'alpha', 0)
