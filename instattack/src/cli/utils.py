import asyncio

from instattack.src.login import LoginHandler
from instattack.src.proxies import ProxyHandler


def post_handlers(user, config):

    lock = asyncio.Lock()
    start_event = asyncio.Event()
    auth_result_found = asyncio.Event()

    proxy_handler = ProxyHandler(
        config['proxies'],
        lock=lock,
        start_event=start_event,
    )

    password_handler = LoginHandler(
        config['login'],
        proxy_handler,
        user=user,
        start_event=start_event,
        stop_event=auth_result_found,
    )
    return proxy_handler, password_handler
