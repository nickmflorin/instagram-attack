"""
[x] NOTE:
--------
Because the ext module is used both at the upper levels by setuptools, the config
and at lower levels in core, it is important that all imports into the files
in these modules be lazy imported.

The functionality in these modules should not depend on functionality elsehwhere
in the app, except for top level constants.
"""
from .framework import remove_pybyte_data, get_app_root, get_root


def clean():
    root = get_app_root()
    print('Cleaning %s' % root)
    remove_pybyte_data(root)


def clean_root():
    root = get_root()
    print('Cleaning %s' % root)
    remove_pybyte_data(root)
