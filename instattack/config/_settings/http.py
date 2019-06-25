from instattack.config import fields

# TODO:
# Join URLS in a Non-Configurable Set Field

# Instagram Constants
INSTAGRAM_URL = 'https://www.instagram.com/'
INSTAGRAM_LOGIN_URL = 'https://www.instagram.com/accounts/login/ajax/'
TEST_POST_URL = "https://postman-echo.com/post"


VERSION = 18
RELEASE = 4.3
MFG = "Xiaomi"
MODEL = "HM 1SW"

# TODO: Come Up with List of User Agents
USERAGENT = (
    f'Instagram 9.2.0 Android ({VERSION}/{RELEASE}; '
    f'320dpi; 720x1280; {MFG}; {MODEL}; armani; qcom; en_US)'
)

# HEADER Has to be Field - Configured w/ Token
# TODO: Restrict configuration to just adding the token.
HEADER = fields.DictField({
    'Referer': INSTAGRAM_URL,
    "User-Agent": USERAGENT,
})

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
