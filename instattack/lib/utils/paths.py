from plumbum.path import LocalPath
import os
import site

from instattack.config import constants


def relative_to_root(path):

    if not isinstance(path, LocalPath):
        path = LocalPath(path)

    # This only happens for the test.py file...  We should remove this conditional
    # when we do not need that functionality anymore.
    if constants.APP_NAME in path.parts:
        ind = path.parts.index(constants.APP_NAME)
        parts = path.parts[ind:]
        path = LocalPath(*parts)

    return constants.DIR_STR(path)


def task_is_third_party(task):
    """
    Need to find a more sustainable way of doing this, this makes
    sure that we are not raising exceptions for external tasks.
    """
    directory = get_task_path(task)
    return not directory.startswith(constants.APP_DIR)


def get_coro_path(coro):
    return coro.cr_code.co_filename


def get_task_path(task):
    return get_coro_path(task._coro)


def path_up_until(path, piece, as_string=True):
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
    if path.startswith(constants.APP_PATH):
        return True
    return False
