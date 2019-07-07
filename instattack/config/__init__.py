import os

from instattack.ext import get_root
from instattack.info import __NAME__

from pkconfig import LazySettings


settings = LazySettings(
    env_keys='INSTATTACK_SIMPLE_SETTINGS',
    settings_dir=os.path.join(get_root(), __NAME__, 'config', 'system')
)
print(settings)
