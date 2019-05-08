from instattack import settings
from instattack.exceptions import DirExists

from .logger import AppLogger
from .paths import get_users_data_dir


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


def _user_data_dir(app_name=True):
    return local.cwd / settings.APP_NAME / settings.USER_DIR


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


# def write_attempts_file(attempts, username):
#     try:
#         path = get_user_file_path(settings.FILENAMES.ATTEMPTS, username,
#             expected=True, strict=True)
#     except UserFileMissing as e:
#         log.warning(str(e))
#         create_user_file(settings.FILENAMES.ATTEMPTS, username, strict=True)
#     write_array_data(path, attempts)


# def update_attempts_file(attempts, username):

#     current_attempts = read_user_file(settings.FILENAMES.ATTEMPTS, username)
#     unique_attempts = 0

#     for attempt in attempts:
#         if attempt not in current_attempts:
#             unique_attempts += 1
#             current_attempts.append(attempt)

#     log.notice(f"Saving {unique_attempts} unique additional attempts.")
#     write_attempts_file(current_attempts, username)
