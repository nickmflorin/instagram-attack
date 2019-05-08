from plumbum import local

from instattack import settings
from instattack.exceptions import (
    DirExists, DirMissing, UserDirMissing, UserDirExists, UserFileMissing,
    UserFileExists)

from .logger import AppLogger


log = AppLogger(__file__)


def _user_data_dir(app_name=True):
    if app_name:
        return local.cwd / settings.APP_NAME / settings.DATA_DIR / settings.USER_DIR
    return local.cwd / settings.DATA_DIR / settings.USER_DIR


def _get_users_data_dir():
    path = _user_data_dir()
    if not path.exists():
        path = _user_data_dir(app_name=False)
    return path


def get_users_data_dir(expected=True, strict=True):
    path = _get_users_data_dir()

    if strict and (not expected and path.exists()):
        raise DirExists("%s/%s" % (path.dirname, path.name))

    elif strict and (expected and not path.exists()):
        raise DirMissing("%s/%s" % (path.dirname, path.name))

    return path


def get_user_data_dir(username, expected=True, strict=True):
    path = get_users_data_dir(expected=True, strict=True) / username

    if strict and (expected and not path.exists()):
        raise UserDirMissing(username)

    elif strict and (not expected and path.exists()):
        raise UserDirExists(username)

    return path


def get_user_file_path(filename, username, expected=True, strict=True):
    if '.txt' not in filename:
        filename = f"{filename}.txt"

    path = get_user_data_dir(username, expected=True, strict=True) / filename

    if strict and (expected and not path.exists()):
        raise UserFileMissing(filename, username)

    elif strict and (not expected and path.exists()):
        raise UserFileExists(username, filename)

    return path
