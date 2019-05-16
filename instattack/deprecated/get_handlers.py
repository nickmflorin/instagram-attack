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


async def get_token(loop, config):
    """
    Uses proxies specifically for GET requests to synchronously make
    requests to the INSTAGRAM_URL until a valid response is received with
    a token that can be used for subsequent stages.

    We cannot perform any actions in finally because if we hit an exception,
    the loop will have been shutdown by that point.

    Proxies will not be saved if it wasn't started, but that is probably
    desired behavior.

    IMPORTANT:
    ---------
    The only reason to potentially use async retrieval of token would be if we
    wanted to use proxies and weren't sure how well the proxies would work.  It
    is much faster to just use a regular request, but does not protect identity.

    For now, we will go the faster route, but leave the code around that found
    the token through iterative async requests for the token.
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

