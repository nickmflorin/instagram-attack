from .utils import get_root, dir_str

# Directory Configuration
APP_NAME = 'instattack'
DB_NAME = APP_NAME

ROOT_DIR = get_root()
USER_DIR = ROOT_DIR / "users"

# Instagram Constants
INSTAGRAM_URL = 'https://www.instagram.com/'
INSTAGRAM_LOGIN_URL = 'https://www.instagram.com/accounts/login/ajax/'

URLS = {
    'GET': INSTAGRAM_URL,
    'POST': INSTAGRAM_LOGIN_URL
}


# Database Configuration
DB_PATH = ROOT_DIR / f"{APP_NAME}.db"
DB_URL = f'sqlite:///{dir_str(DB_PATH)}'

DB_CONFIG = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.sqlite',
            'credentials': {
                'file_path': DB_PATH,
                'database': APP_NAME,
            }
        },
    },
    'apps': {
        'models': {
            'models': [
                'instattack.proxies.models',
                'instattack.users.models',
            ],
            'default_connection': 'default',
        }
    }
}

VERSION = 18
RELEASE = 4.3
MFG = "Xiaomi"
MODEL = "HM 1SW"

# TODO: Come Up with List of User Agents
USERAGENT = (
    f'Instagram 9.2.0 Android ({VERSION}/{RELEASE}; '
    f'320dpi; 720x1280; {MFG}; {MODEL}; armani; qcom; en_US)'
)

# Instagram Requests
HEADER = {
    'Referer': 'https://www.instagram.com/',
    "User-Agent": USERAGENT,
    # 'Content-Type': 'application/x-www-form-urlencoded',
}


def HEADERS(token=None):
    headers = HEADER.copy()
    if token:
        headers["X-CSRFToken"] = token
    return headers


# Proxies Constants
PROXY_COUNTRIES = {
    'GET': [],
    'POST': [],
}
PROXY_TYPES = {
    'GET': ['HTTP'],
    'POST': ['HTTP'],
}
PROXY_POST = {
    'GET': False,
    'POST': True,
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
