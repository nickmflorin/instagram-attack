from __future__ import absolute_import


__all__ = ('get_token_from_cookies', 'get_cookies_from_response',
    'get_token_from_response')


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
