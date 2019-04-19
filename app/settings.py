from __future__ import absolute_import

from app.lib.utils import create_url


# User Management
PASSWORD_FILENAME = "passwords"
ATTEMPTS_FILENAME = "attempts"
ALTERATIONS_FILENAME = "alterations"
NUMBERS_FILENAME = "common_numbers"
USER_DIRECTORY = "users"

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


TEST_URL = 'https://api6.ipify.org?format=json'

# Instagram Requests
HEADER = {
    'Referer': 'https://www.instagram.com/',
    'Content-Type': 'application/x-www-form-urlencoded',
}
TOKEN_HEADER = 'x-csrftoken'

INSTAGRAM_URL = 'https://www.instagram.com/'
INSTAGRAM_LOGIN_URL = 'https://www.instagram.com/accounts/login/ajax/'

INSTAGRAM_USERNAME_FIELD = 'username'
INSTAGRAM_PASSWORD_FIELD = 'password'

# Instagram Response
CHECKPOINT_REQUIRED = "checkpoint_required"
GENERIC_REQUEST_ERROR = 'generic_request_error'
GENERIC_REQUEST_MESSAGE = 'Sorry, there was a problem with your request.'

# Make Overrideable from Config
PROXY_HOST = '127.0.0.1'

GET_PORT = 8881
POST_PORT = 8882

GET_URL = create_url(PROXY_HOST, GET_PORT)
POST_URL = create_url(PROXY_HOST, POST_PORT)


GET_BROKER_CONFIG = {
    'max_tries': 3,
    'max_conn': 100,
}

POST_BROKER_CONFIG = {
    'max_tries': 3,
    'max_conn': 400,
}

GET_SERVER_CONFIG = {
    'types': [('HTTP', 'High'), 'HTTPS', 'CONNECT:80'],
    'http_allowed_codes': [200, 301, 302, 400],
    'limit': 100,
    'prefer_connect': False,
    'min_req_proxy': 5,
    'max_error_rate': 0.5,
    'max_resp_time': 8,
    'backlog': 100,
    'host': PROXY_HOST,
    'port': GET_PORT,
}

POST_BROKER_MAX_RETRIES = 1

POST_SERVER_CONFIG = {
    'types': [('HTTP', 'High'), 'HTTPS', 'CONNECT:80'],
    'http_allowed_codes': [200, 201, 301, 302, 400],
    'limit': 200,
    'prefer_connect': False,
    'min_req_proxy': 5,
    'max_error_rate': 0.5,
    'max_resp_time': 8,
    'backlog': 100,
    'post': True,
    'host': PROXY_HOST,
    'port': POST_PORT,
}

TEST_GET_REQUEST_URL = 'https://postman-echo.com/get'
TEST_POST_REQUEST_URL = 'https://postman-echo.com/post'
