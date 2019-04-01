from __future__ import absolute_import


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


HEADER = {
    'referer': 'https://www.instagram.com/',
    'content-type': 'application/x-www-form-urlencoded'
}

INSTAGRAM_USERNAME_FIELD = 'username'
INSTAGRAM_PASSWORD_FIELD = 'password'

INSTAGRAM_URL = 'https://www.instagram.com/'
INSTAGRAM_LOGIN_URL = 'https://www.instagram.com/accounts/login/ajax/'

DEFAULT_FETCH_TIME = 6
DEFAULT_TOKEN_FETCH_TIME = 4
DEFAULT_LOGIN_FETCH_TIME = 8


PROXY_LINKS = [
    'https://sslproxies.org',
    'https://free-proxy-list.net',
    'https://free-proxy-list.net/anonymous-proxy.html'
]
EXTRA_PROXY = 'http://spys.me/proxy.txt'

PASSWORD_FILENAME = "passwords"
ATTEMPTS_FILENAME = "attempts"
ALTERATIONS_FILENAME = "alterations"
NUMBERS_FILENAME = "common_numbers"
USER_DIRECTORY = "users"

CHECKPOINT_REQUIRED = "checkpoint_required"
GENERIC_REQUEST_ERROR = 'generic_request_error'
