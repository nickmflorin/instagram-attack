from setuptools import setup, find_packages
from pip._internal.req import parse_requirements
import os

"""
[x] NOTE:
--------
Once any import from instattack is performed, simple_settings are lazily initialized
with the `INSTATTACK_SIMPLE_SETTINGS` ENV variable.  If `INSTATTACK_SIMPLE_SETTINGS`
is not set, it uses `dev` by default.

This means that if we want to use another settings file, we have to specify the
ENV variable before any import from instattack is performed.
"""

reqs = parse_requirements('./requirements.txt', session=False)
install_requires = [str(ir.req) for ir in reqs]

os.environ['INSTATTACK_SIMPLE_SETTINGS'] = 'dev'

from instattack import settings  # noqa
from termx.library import get_version  # noqa

f = open('README.md', 'r')
LONG_DESCRIPTION = f.read()
f.close()

setup(
    name=settings.NAME,
    version=get_version(settings.APP_VERSION),
    description=settings.FORMAL_NAME,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    author='Nick Florin',
    author_email='nickmflorin@gmail.com',
    url='https://github.com/nickmflorin/instagram-attack',
    license='unlicensed',
    packages=find_packages(exclude=['ez_setup', 'tests*']),
    package_dir={'instattack': 'instattack'},
    package_data={'instattack': ['templates/*']},
    include_package_data=True,
    install_requires=install_requires,
    entry_points="""
        [console_scripts]
        instattack = instattack.main:instattack
        playground = instattack.main:run_playground
        clean = instattack.main:clean
        cleanroot = instattack.main:cleanroot
    """,
)
