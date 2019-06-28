"""
[!] VERY IMPORTANT
-----------------
Defining the simple_settings lazily will ensure that we are not mixing them with
other packages that we use in tandem.

>>> from instattack import settings

instead of

>>> from simple_settings import settings
"""
import os
os.environ['INSTATTACK_SIMPLE_SETTINGS'] = 'dev'

from .config import settings  # noqa
