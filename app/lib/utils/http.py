from __future__ import absolute_import


__all__ = ('format_proxy', 'get_token_from_cookies', 'get_cookies_from_response',
    'get_token_from_response')


def format_proxy(proxy, scheme='http'):
    return f"{scheme}://{proxy.host}:{proxy.port}/"


def get_token_from_cookies(cookies):
    # aiohttp ClientResponse cookies have .value attribute.
    cookie = cookies.get('csrftoken')
    if cookie:
        try:
            return cookie.value
        except AttributeError:
            return cookie


def get_cookies_from_response(response):
    return response.cookies


def get_token_from_response(response):
    cookies = get_cookies_from_response(response)
    if cookies:
        return get_token_from_cookies(cookies)
