from __future__ import absolute_import

from argparse import ArgumentParser
import os

from app import settings
from app.exceptions import ApiBadProxyException, InstagramClientException
from app.lib.users import User, Users
from app.lib.api import ProxyApi, InstagramApi


def test_get_proxies():

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = proxy_api.get_proxies()
    for proxy in proxies:
        print(proxy)

def get_api_token(user):
    token = None
    proxy_count = 0

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = list(proxy_api.get_proxies())

    while token is None and proxy_count <= len(proxies) - 1:
        proxy = proxies[proxy_count]
        api = InstagramApi(user.username, proxy)
        try:
            token = api.refresh_token()
        except ApiBadProxyException:
            print(f"Bad Proxy Found in Test {proxy}")
            proxy_count += 1
        else:
            if token is not None:
                print(f"Got Token in Test {token}")
                print(f"Got Proxy in Test {proxy}")
                return token, proxy

def test_get_token():

    user = User('nickmflorin')
    passwords = user.get_raw_passwords()

    token, api = get_api_token(user)
    api = InstagramApi(user.username, proxy)

    count = 0
    while count <= len(passwords) - 1:
        password = passwords[count]
        try:
            results = api.login(password, token=token)
            print(results)
        except ApiBadProxyException:
            print("Bad proxy logging in user.")
            break
        except InstagramClientException as e:
            print("Hit error logging in user.")
            print(str(e))
            break
        else:
            count += 1


def test_create_user():
    username = "testuser"
    Users.create(username)


def test_get_passwords():
    username = "testuser"
    user = User(username)
    passwords = user.get_raw_passwords()
    print(passwords)


def test_get_attempts():
    username = "testuser"
    user = User(username)
    attempts = user.get_password_attempts()
    print(attempts)


def test_update_attempts():
    username = "testuser"
    attempts = ['first', 'second', 'third', 'fourth', 'fifth']
    user = User(username)
    user.update_password_attempts(attempts)


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
