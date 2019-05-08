from instattack import settings
from instattack.exceptions import (
    UserFileMissing, UserDirMissing, DirExists, DirMissing)

from .logger import AppLogger
from .io import write_array_data, read_raw_data
from .paths import get_users_data_dir, get_user_data_dir, get_user_file_path


log = AppLogger(__file__)

"""
Some useful code playing around with file permissions and plumbum.  We shouldn't
have permission issues so as long as these files are created inside the Python
app and not by the root user.

-----------------
Effective Group ID: os.getegid()
Real Group ID: os.geteuid()
Effective User ID:  os.getgid()

------
Changing File Modes and Permissions

os.chmod(filename, 0o644)

file.chmod(stat.S_IWRITE)
path.chmod(777)
newpath.chown(owner=os.geteuid(), group=os.getgid())
"""

"""
Some of these checks might not be necessary because we check the existence of
a user based on the presence of the username folder, so checking if that exists
after using it to determine if the user exists is redundant.  But it keeps the
control flow consistent and over cautious is never a bad thing.
"""


def create_users_data_dir(strict=True):
    try:
        path = get_users_data_dir(expected=False)
    except DirExists as e:
        if strict:
            raise e
        log.warning(str(e))
    else:
        path.mkdir()
        return path


def create_user_dir(username, strict=True):

    user_path = get_user_data_dir(username, expected=False, strict=strict)
    user_path.mkdir()
    return user_path


def create_user_file(filename, username, strict=True):

    filepath = get_user_file_path(filename, username, expected=False, strict=strict)
    filepath.touch()


def create_new_user_files(username):
    """
    Called when creating a new user.
    """
    for filename in settings.USER_FILES:
        create_user_file(filename, username, strict=True)


def check_user_files(username):
    """
    Called if the user already exists but we want to double check to make sure
    all files are present.
    """
    try:
        get_users_data_dir(expected=True, strict=True)
    except DirMissing as e:
        log.warning(str(e))
        create_users_data_dir(strict=True)

    try:
        get_user_data_dir(username, expected=True, strict=True)
    except UserDirMissing as e:
        log.warning(str(e))
        create_user_dir(username, strict=True)

    for filename in settings.USER_FILES:
        try:
            get_user_file_path(filename, username, expected=True, strict=True)
        except UserFileMissing as e:
            log.warning(str(e))
            create_user_file(filename, username, strict=True)


def read_user_file(filename, username):
    """
    TODO:
    -----

    If the package downloader for whatever reason deletes these files, we should
    issue a warning and recreate them.
    """
    filepath = get_user_file_path(filename, username)
    if not filepath.is_file():
        raise FileNotFoundError('No such file: %s' % filepath)
    return read_raw_data(filepath)


def write_attempts_file(attempts, username):
    try:
        path = get_user_file_path(settings.FILENAMES.ATTEMPTS, username,
            expected=True, strict=True)
    except UserFileMissing as e:
        log.warning(str(e))
        create_user_file(settings.FILENAMES.ATTEMPTS, username, strict=True)
    write_array_data(path, attempts)


def update_attempts_file(attempts, username):

    current_attempts = read_user_file(settings.FILENAMES.ATTEMPTS, username)
    unique_attempts = 0

    for attempt in attempts:
        if attempt not in current_attempts:
            unique_attempts += 1
            current_attempts.append(attempt)

    log.notice(f"Saving {unique_attempts} unique additional attempts.")
    write_attempts_file(current_attempts, username)


def user_exists(username):
    try:
        get_users_data_dir(expected=True, strict=True)
    except DirMissing as e:
        return False

    try:
        get_user_data_dir(username, expected=True, strict=True)
    except UserDirMissing:
        return False

    return True
