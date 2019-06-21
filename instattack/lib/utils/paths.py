import pathlib
import site

from termx.library import path_up_until
from instattack.ext import get_app_root


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


def is_log_file(path):
    pt = pathlib.PurePath(path)
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
