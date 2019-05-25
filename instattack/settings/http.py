# Instagram Constants
INSTAGRAM_URL = 'https://www.instagram.com/'
INSTAGRAM_LOGIN_URL = 'https://www.instagram.com/accounts/login/ajax/'

URLS = {
    'GET': INSTAGRAM_URL,
    'POST': INSTAGRAM_LOGIN_URL
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


ERROR_TRANSLATION = {
    'ClientProxyConnectionError': 'proxy_connection',
    'ClientConnectorError': 'client_connection',
    'ServerConnectionError': 'server_connection',
    'ClientConnectorError': 'client_connection',
    'ClientConnectorCertificateError': 'ssl',
    'ClientConnectorSSLError': 'ssl',
    'ConnectionResetError': 'server_connection',
    'ConnectionRefusedError': 'server_connection',
    'SSLError': 'ssl',
    'ClientResponseError': 'invalid_response',
}

CONNECTION_ERRORS = (
    'client_connection',
    'proxy_connection',
    'server_connection',
)
