"""
This module is only for developer environments.

Creating a sub-module where we can store test code, duplicate and modified versions
of existing code and explore programming possibilities is a crucial part of
this project.

It is in this module where we play around with certain packages, code and
ideas, not being in the Cement app framework but still having access to the
components that make up the instattack app.
"""


def playground():
    from pkconfig import fields
    import os

    from instattack.ext import get_root
    from instattack.info import __NAME__

    from pkconfig import LazySettings

    settings = LazySettings(
        env_keys='INSTATTACK_SIMPLE_SETTINGS',
        settings_dir=os.path.join(get_root(), __NAME__, 'config', 'system')
    )
    print(settings)
