#!/usr/bin/env python3 -B

from setuptools import setup, find_packages

import sys
import os

sys.dont_write_bytecode = True
os.system("export PYTHONDONTWRITEBYTECODE=yes")


setup(
    name="instattack",
    version="0.0.1",
    description="Brute Force Attacking Instagram",
    author="Anonymous",
    author_email="anonymous@gmail.com",
    url="https://github.com/nickmflorin/instagram-attack",
    packages=find_packages(),
    # Have to add a lot here
    install_requires=[
        'plumbum',
    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'manage = instattack.__main__:main',
        ],
    },
    zip_safe=False
)