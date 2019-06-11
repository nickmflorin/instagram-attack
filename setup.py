from setuptools import setup, find_packages
from instattack.version import get_version

VERSION = get_version()

f = open('README.md', 'r')
LONG_DESCRIPTION = f.read()
f.close()

setup(
    name='instattack',
    version=VERSION,
    description='Instattack',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    author='Nick Florin',
    author_email='nickmflorin@gmail.com',
    url='https://github.com/nickmflorin/instagram-attack',
    license='unlicensed',
    packages=find_packages(exclude=['ez_setup', 'tests*']),
    package_data={'instatttack': ['templates/*']},
    include_package_data=True,
    entry_points="""
        [console_scripts]
        instattack = instattack.main:main
    """,
)
