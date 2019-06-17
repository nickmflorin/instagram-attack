from setuptools import setup, find_packages
from instattack import __NAME__, __FORMAL_NAME__
from instattack.config import config


VERSION = config.version()

f = open('README.md', 'r')
LONG_DESCRIPTION = f.read()
f.close()

setup(
    name=__NAME__,
    version=VERSION,
    description=__FORMAL_NAME__,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    author='Nick Florin',
    author_email='nickmflorin@gmail.com',
    url='https://github.com/nickmflorin/instagram-attack',
    license='unlicensed',
    packages=find_packages(exclude=['ez_setup', 'tests*']),
    package_data={'instattack': ['templates/*']},
    include_package_data=True,
    entry_points="""
        [console_scripts]
        instattack = instattack.main:instattack
        playground = instattack.main:playground
        clean = instattack.ext.scripts:clean
        cleanroot = instattack.ext.scripts:clean_root
    """,
)
