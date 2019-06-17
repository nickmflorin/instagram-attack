from plumbum.path import LocalPath
import os
import site

from instattack import __NAME__
from instattack.config import constants
from instattack.ext import get_app_root


def relative_to_root(path):
    """
    [x] TODO:
    --------
    Deprecate use of plumbum.path.LocalPath and start incorporating pathlib
    more consistently.
    """
    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    # This only happens for the test.py file...  We should remove this conditional
    # when we do not need that functionality anymore.
    if __NAME__ in path.parts:
        ind = path.parts.index(__NAME__)
        parts = path.parts[ind:]
        path = LocalPath(*parts)

    return constants.DIR_STR(path)


def task_is_third_party(task):
    """
    Need to find a more sustainable way of doing this, this makes
    sure that we are not raising exceptions for external tasks.
    """
    directory = get_task_path(task)
    app_dir = get_app_root()
    return not directory.startswith(app_dir)


def get_coro_path(coro):
    return coro.cr_code.co_filename


def get_task_path(task):
    return get_coro_path(task._coro)


def path_up_until(path, piece, as_string=True):
    """
    [x] TODO:
    --------
    Deprecate use of plumbum.path.LocalPath and start incorporating pathlib
    more consistently.
    """
    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    if piece not in path.parts:
        raise ValueError(f'The path does not contain the piece {piece}.')

    index = path.parts.index(piece)
    parts = path.parts[:index + 1]
    full_path = os.path.join('/', *parts)
    if as_string:
        return full_path
    return LocalPath(full_path)


def is_log_file(path):
    """
    [x] TODO:
    --------
    Deprecate use of plumbum.path.LocalPath and start incorporating pathlib
    more consistently.
    """
    pt = LocalPath(path)
    if 'logger' in pt.parts:
        log_file_path = path_up_until(path, 'logger')
        if path.startswith(log_file_path):
            return True
    return False


def is_site_package_file(path):
    site_packages = site.getsitepackages()
    for site_package in site_packages:
        if path.startswith(site_package):
            return True
    return False


def is_app_file(path):
    app_dir = get_app_root()
    if path.startswith(app_dir):
        return True
    return False
