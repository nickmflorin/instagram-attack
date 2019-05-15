#!/usr/bin/env python3 -B

from setuptools import setup, find_packages

setup(
    name="instattack",
    version="0.0.1",
    description="Brute Force Attacking Instagram",
    author="Nick Florin",
    author_email="nickmflorin@gmail.com",
    url="https://github.com/nickmflorin/instagram-attack",
    packages=find_packages(),
    install_requires=[
        'aiodns',
        'aiosqlite',
        'aiofiles',
        'aiohttp',
        'asyncio',
        'maxminddb',
        'proxybroker',
        'plumbum',
        'tortoise-orm',
        'PyYAML',
    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'manage = instattack.__main__:main',
        ],
    },
    zip_safe=False
)
