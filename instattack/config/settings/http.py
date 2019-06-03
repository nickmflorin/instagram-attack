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

# Instagram Requests
HEADER = {
    'Referer': 'https://www.instagram.com/',
    "User-Agent": USERAGENT,
}


def HEADERS(token=None):
    headers = HEADER.copy()
    if token:
        headers["X-CSRFToken"] = token
    return headers
