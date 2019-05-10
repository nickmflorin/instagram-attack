from plumbum import local

from instattack import settings


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


def get_data_dir():
    """
    TODO:
    ----
    Find a way to make this relative so we do not get stuck if we are running
    commands from nested portions of the app.
    """
    path = local.cwd / settings.USER_DIR
    if not path.exists():
        path.mkdir()
    return path
