"""
[x] NOTE:
--------
Because the ext module is used both at the upper levels by setuptools, the config
and at lower levels in core, it is important that all imports into the files
in these modules be lazy imported.

The functionality in these modules should not depend on functionality elsehwhere
in the app, except for top level constants.

[x] THIS FILE
------------
This file should contain utilities that are meant solely for private use
with in the package.

Utilities meant for use both inside the package and by potential users should
be placed in the utils.py file (if any).
"""

import datetime
import os
import pathlib
import subprocess


def find_first_parent(path, name):
    """
    Given a path and the name of a parent directory, incrementally moves upwards
    in the filesystem, directory by directory, until either the root is reached
    (when the parent is not changing) or the directory reached has the desired
    parent name.
    """
    parent = pathlib.PurePath(path)

    while True:
        new_parent = parent.parent
        if new_parent.name == name:
            return new_parent
        # At the root: PurePosixPath('/'), path.parent = path.parent.parent.
        elif new_parent == parent:
            return new_parent
        else:
            parent = new_parent


def get_root():
    """
    Given the path of the file calling the function, incrementally moves up
    directory by directory until either the root is reached (when the parent
    is not changing) or the directory reached has the name associated with
    the app name.

    When we reach the directory associated with the app directory, the root
    is the path's parent.
    """
    from instattack import __NAME__

    path = os.path.dirname(os.path.realpath(__file__))
    parent = find_first_parent(path, __NAME__)
    return str(parent.parent)


def get_app_root():
    from instattack import __NAME__
    root = get_root()
    return os.path.join(root, __NAME__)


def get_root_file_path(filename, ext=None):
    if ext:
        filename = "%s.%s" % (filename, ext)
    root = get_root()
    return os.path.join(root, filename)


def get_version(version):
    """
    Returns a PEP 386-compliant version number from VERSION.
    """
    if len(version) != 5 or version[3] not in ('alpha', 'beta', 'rc', 'final'):
        raise ValueError('Invalid version %s.' % version)

    # Now build the two parts of the version number:
    # main = X.Y[.Z]
    # sub = .devN - for pre-alpha releases
    #     | {a|b|c}N - for alpha, beta and rc releases

    # We want to explicitly include all three version/release numbers
    # parts = 2 if version[2] == 0 else 3
    parts = 3
    main = '.'.join(str(x) for x in version[:parts])

    sub = ''
    if version[3] == 'alpha' and version[4] == 0:
        git_changeset = get_git_changeset()
        if git_changeset:
            sub = '.dev%s' % git_changeset

    elif version[3] != 'final':
        mapping = {'alpha': 'a', 'beta': 'b', 'rc': 'c'}
        sub = mapping[version[3]] + str(version[4])

    return main + sub


def get_git_changeset():
    """
    Returns a numeric identifier of the latest git changeset.
    The result is the UTC timestamp of the changeset in YYYYMMDDHHMMSS format.

    This value isn't guaranteed to be unique, but collisions are very
    unlikely, so it's sufficient for generating the development version
    numbers.
    """
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.Popen('git log --pretty=format:%ct --quiet -1 HEAD',
       stdout=subprocess.PIPE,
       stderr=subprocess.PIPE,
       shell=True,
       cwd=repo_dir,
       universal_newlines=True)

    timestamp = git_log.communicate()[0]
    try:
        timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))
    except ValueError:  # pragma: nocover
        return None     # pragma: nocover
    return timestamp.strftime('%Y%m%d%H%M%S')


def remove_pybyte_data(*paths):

    def _remove_pybyte_data(pt):
        [p.unlink() for p in pathlib.Path(pt).rglob('*.py[co]')]
        [p.rmdir() for p in pathlib.Path(pt).rglob('__pycache__')]

    [_remove_pybyte_data(pt) for pt in paths]
