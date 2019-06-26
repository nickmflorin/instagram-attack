from setuptools import setup, find_packages
from pip._internal.req import parse_requirements
import os
import subprocess
import sys

sys.path.append("./termx/termx")


"""
[x] NOTE:
--------
Once any import from instattack is performed, simple_settings are lazily initialized
with the `INSTATTACK_SIMPLE_SETTINGS` ENV variable.  If `INSTATTACK_SIMPLE_SETTINGS`
is not set, it uses `dev` by default.

This means that if we want to use another settings file, we have to specify the
ENV variable before any import from instattack is performed.
"""

os.environ['INSTATTACK_SIMPLE_SETTINGS'] = 'dev'


def get_requirements(requirements_file='./requirements.txt'):
    reqs = parse_requirements(requirements_file, session=False)
    return [str(ir.req) for ir in reqs]


def install(package):
    """
    Runs the same python executable running the code and tells it to execute
    the pip module it has installed.
    """
    subprocess.call([sys.executable, "-m", "pip", "install", package])


def install_requirements():
    reqs = get_requirements()
    for module_name in reqs:
        install(module_name)

# from instattack import settings  # noqa
# from termx.library import get_version  # noqa
from temputils import get_version

# try:
#     from instattack import settings  # noqa
#     # from termx.library import get_version  # noqa
#     from .temputils import get_version
# except ModuleNotFoundError:
#     print('Missing Module')
#     # install_requirements()

# finally:
#     from instattack import settings  # noqa
#     from termx.library import get_version  # noqa


f = open('README.md', 'r')
LONG_DESCRIPTION = f.read()
f.close()

NAME = 'instattack'
FORMAL_NAME = NAME.title()
APP_VERSION = (0, 0, 1, 'alpha', 0)


setup(
    name=NAME,
    version=get_version(APP_VERSION),
    description=FORMAL_NAME,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    author='Nick Florin',
    author_email='nickmflorin@gmail.com',
    url='https://github.com/nickmflorin/instagram-attack',
    license='unlicensed',
    packages=find_packages(exclude=['ez_setup', 'tests*']),
    package_dir={
        'instattack': 'instattack',
        # 'termx': 'termx',
    },
    package_data={'instattack': ['templates/*']},
    include_package_data=True,
    entry_points="""
        [console_scripts]
        instattack = instattack.main:instattack
        playground = instattack.main:run_playground
        clean = instattack.main:clean
        cleanroot = instattack.main:cleanroot
    """,
)
