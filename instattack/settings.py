from __future__ import absolute_import

from argparse import ArgumentTypeError
from plumbum import local

from .exceptions import (
    DirExists, DirMissing, UserDirMissing, UserDirExists, UserFileMissing, UserFileExists)


USER_AGENTS = [
    'Googlebot/2.1 (+http://www.google.com/bot.html)',
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Safari/537.36',  # noqa
    'Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; Google Web Preview Analytics) Chrome/27.0.1453 Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_3 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/8.0 Mobile/12F70 Safari/600.1.4 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 8_3 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12F70 Safari/600.1.4 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',  # noqa
    'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 6_0 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5376e Safari/8536.25 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',  # noqa
    'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.96 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',  # noqa


    'Mozilla/5.0 (compatible; bingbot/2.0;  http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (compatible; adidxbot/2.0;  http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (compatible; adidxbot/2.0; +http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (seoanalyzer; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) SitemapProbe',
    'Mozilla/5.0 (Windows Phone 8.1; ARM; Trident/7.0; Touch; rv:11.0; IEMobile/11.0; NOKIA; Lumia 530) like Gecko (compatible; adidxbot/2.0; +http://www.bing.com/bingbot.htm)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 7_0 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11A465 Safari/9537.53 (compatible; adidxbot/2.0;  http://www.bing.com/bingbot.htm)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 7_0 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11A465 Safari/9537.53 (compatible; adidxbot/2.0; +http://www.bing.com/bingbot.htm)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 7_0 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11A465 Safari/9537.53 (compatible; bingbot/2.0;  http://www.bing.com/bingbot.htm)',  # noqa
    'Mozilla/5.0 (iPhone; CPU iPhone OS 7_0 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11A465 Safari/9537.53 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',  # noqa
]

APP_NAME = 'instattack'
USER_DIR = "users"
DATA_DIR = "data"
PROXY_DIR = "proxies"


class FILENAMES(object):

    PASSWORDS = "passwords"
    ATTEMPTS = "attempts"
    ALTERATIONS = "alterations"
    NUMBERS = "common_numbers"


USER_FILES = [FILENAMES.PASSWORDS, FILENAMES.ATTEMPTS, FILENAMES.NUMBERS,
    FILENAMES.ALTERATIONS]


# Instagram Requests
HEADER = {
    'Referer': 'https://www.instagram.com/',
    'Content-Type': 'application/x-www-form-urlencoded',
}
TOKEN_HEADER = 'x-csrftoken'

INSTAGRAM_USERNAME_FIELD = 'username'
INSTAGRAM_PASSWORD_FIELD = 'password'

# Instagram Response
CHECKPOINT_REQUIRED = "checkpoint_required"
GENERIC_REQUEST_ERROR = 'generic_request_error'
GENERIC_REQUEST_MESSAGE = 'Sorry, there was a problem with your request.'

INSTAGRAM_URL = 'https://www.instagram.com/'
INSTAGRAM_LOGIN_URL = 'https://www.instagram.com/accounts/login/ajax/'

URLS = {
    'GET': INSTAGRAM_URL,
    'POST': INSTAGRAM_LOGIN_URL
}

TEST_GET_REQUEST_URL = 'https://postman-echo.com/get'
TEST_POST_REQUEST_URL = 'https://postman-echo.com/post'

TEST_URLS = {
    'GET': TEST_GET_REQUEST_URL,
    'POST': TEST_POST_REQUEST_URL
}

# General
LEVELS = [
    'INFO',
    'DEBUG',
    'WARNING',
    'SUCCESS',
    'CRITICAL',
]

METHODS = ['GET', 'POST']


def validate_log_level(val):
    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in LEVELS:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


def validate_method(value):
    if value.upper() not in METHODS:
        raise ArgumentTypeError('Invalid method.')
    return value.upper()


def _proxy_file_dir(app_name=True):
    if app_name:
        return local.cwd / APP_NAME / PROXY_DIR / DATA_DIR
    return local.cwd / PROXY_DIR / DATA_DIR


def _user_data_dir(app_name=True):
    if app_name:
        return local.cwd / APP_NAME / USER_DIR / DATA_DIR
    return local.cwd / USER_DIR / DATA_DIR


def _get_proxy_data_dir():
    path = _proxy_file_dir()
    if not path.exists():
        path = _proxy_file_dir(app_name=False)
    return path


def _get_users_data_dir():
    path = _user_data_dir()
    if not path.exists():
        path = _user_data_dir(app_name=False)
    return path


def get_proxy_file_path(method):
    """
    `app_name` just allows us to run commands from the level deeper than the root
    directory.

    TODO: Incorporate the checks just in case we have to construct the files and
    directories
    """
    path = _get_proxy_data_dir()

    validate_method(method)
    filename = "%s.txt" % method.lower()
    return path / filename


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
