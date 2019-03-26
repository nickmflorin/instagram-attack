from __future__ import absolute_import

from argparse import ArgumentParser
import os

from app import settings
from app.lib.api import ProxyApi, InstagramApi


def test_get_proxies():

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = proxy_api.get_proxies()
    for proxy in proxies:
        print(proxy)


def test_get_token():
    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = list(proxy_api.get_proxies())

    with open('passwords.txt', 'rt', encoding='utf-8') as password_file:
        for password in password_file:
            password = password.replace('\n', '').replace('\r', '').replace('\t', '')

            api = InstagramApi('nickmflorin', proxies[0])
            results = api.login('Whispering1')
            print(results)


def get_args():
    args = ArgumentParser()
    args.add_argument('method', help='Test method to run.')
    return args.parse_args()


if __name__ == '__main__':

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    arugments = get_args()

    # Probably not the best way to do this, but we'll worry about that later.
    method = eval(arugments.method)
    method.__call__()
