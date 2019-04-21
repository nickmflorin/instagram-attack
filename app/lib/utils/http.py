from __future__ import absolute_import


def create_url(host, port, scheme='http'):
    return f'{scheme}://{host}:{port}/'


def get_token_from_cookies(cookies):
    # aiohttp ClientResponse cookies have .value attribute.
    cookie = cookies.get('csrftoken')
    if cookie:
        return cookie.value


def get_cookies_from_response(response):
    return response.cookies


def get_token_from_response(response):
    cookies = get_cookies_from_response(response)
    if cookies:
        return get_token_from_cookies(cookies)
