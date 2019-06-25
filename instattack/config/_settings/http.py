from instattack.config import fields

# [x] TODO:
# --------
# Start generating list of user-agents and using them randomly.

_VERSION = 18
_RELEASE = 4.3
_MFG = "Xiaomi"
_MODEL = "HM 1SW"


INSTAGRAM = fields.SetField(
    URLS=fields.SetField(
        HOME='https://www.instagram.com/',
        LOGIN='https://www.instagram.com/accounts/login/ajax/',
        TEST="https://postman-echo.com/post",
        configurable=False,
    ),
    REQUEST=fields.SetField(
        FIELDS=fields.SetField(
            USERNAME='username',
            PASSWORD='password',
            configurable=False,
        ),
        USERAGENT=(
            f'Instagram 9.2.0 Android ({_VERSION}/{_RELEASE}; '
            f'320dpi; 720x1280; {_MFG}; {_MODEL}; armani; qcom; en_US)'
        ),
        configurable=False,
    ),
    FIELDS=fields.SetField(
        USERNAME='username',
        PASSWORD='password',
        configurable=False,
    ),
    RESPONSE=fields.SetField(
        CHECKPOINT_REQUIRED="checkpoint_required",
        GENERIC_REQUEST_ERROR='generic_request_error',
        GENERIC_REQUEST_MESSAGE='Sorry, there was a problem with your request.',
        configurable=False,
    ),
    # Only Headers Are Configurable
    configurable=True,
)


# TODO: Come Up with List of User Agents
USERAGENT = (
    f'Instagram 9.2.0 Android ({_VERSION}/{_RELEASE}; '
    f'320dpi; 720x1280; {_MFG}; {_MODEL}; armani; qcom; en_US)'
)

# HEADER Has to be Field - Configured w/ Token
HEADERS = fields.PersistentDictField(
    {
        'Referer': INSTAGRAM.urls.home,
        "User-Agent": USERAGENT,
    },
    keys={
        'allowed': ('Referer', 'User-Agent', 'X-CSRFToken'),
        'type': str,
    },
    values={
        'type': str,
    },
    configurable=True,
)

INSTAGRAM.REQUEST.__addfields__(HEADERS=HEADERS)

# TODO: Get descriptions of each field from aiohttp docs.
CONNECTION = fields.SetField(
    LIMIT_PER_HOST=fields.PositiveIntField(
        max=10,
        default=0,
        help="Need to retrieve from aiohttp docs."
    ),
    CONNECTION_TIMEOUT=fields.PositiveIntField(
        max=20,
        default=5,
        help="Need to retrieve from aiohttp docs."
    ),
    CONNECTION_LIMIT=fields.PositiveIntField(
        max=100,
        default=0,
        help="Need to retrieve from aiohttp docs."
    )
)
