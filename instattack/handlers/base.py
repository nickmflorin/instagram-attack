import asyncio
import aiohttp
import random
from urllib.parse import urlparse

from instattack import settings
from instattack.lib import LoggableMixin, get_token_from_response
from instattack.exceptions import (
    TokenNotInResponse, ResultNotInResponse, InstagramResultError)
from instattack.models import InstagramResult


class HandlerMixin(LoggableMixin):

    def engage(self, lock=None, start_event=None, stop_event=None,
            user=None, queue=None):

        self._stopped = False
        self._started = False

        self.lock = lock

        # TODO: Figure out how to incorporate the start_event into the behavior
        # of the stopped property.
        self.stop_event = stop_event
        self.start_event = start_event

        self.user = user
        self.queue = queue


class MethodHandlerMixin(HandlerMixin):

    def engage(self, method=None, **kwargs):
        self.__method__ = method
        super(MethodHandlerMixin, self).engage(**kwargs)

    @property
    def scheme(self):
        scheme = urlparse(settings.URLS[self.__method__]).scheme
        return scheme.upper()


class BaseHandler(object):

    def __init__(self, **kwargs):
        self.engage(**kwargs)


class Handler(BaseHandler, HandlerMixin):
    pass


class MethodHandler(BaseHandler, MethodHandlerMixin):
    pass


class RequestHandler(MethodHandler):

    _user_agent = None

    def __init__(
        self,
        proxy_handler,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None,
        **kwargs,
    ):
        super(RequestHandler, self).__init__(**kwargs)

        self.proxy_handler = proxy_handler

        self._connection_limit = connection_limit
        self._session_timeout = session_timeout
        self._connection_force_close = connection_force_close
        self._connection_limit_per_host = connection_limit_per_host
        self._connection_keepalive_timeout = connection_keepalive_timeout

    @property
    def user_agent(self):
        if not self._user_agent:
            self._user_agent = random.choice(settings.USER_AGENTS)
        return self._user_agent

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def _connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=self._connection_force_close,
            limit=self._connection_limit,
            limit_per_host=self._connection_limit_per_host,
            keepalive_timeout=self._connection_keepalive_timeout,
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self._session_timeout
        )

    def maintain_proxy(self, proxy):
        """
        >>> Not sure if using these callbacks versus just creating the tasks immediately
        >>> in the async func makes a huge difference, but we'll keep for now.
        """
        proxy.just_used()
        asyncio.create_task(self.proxy_handler.pool.put(proxy))

    def add_proxy_error(self, proxy, e):
        """
        Since errors are stored as foreign keys and not on the proxy, we
        have to save them.  That is a lot of database transactions that
        slow down the process of finding the token.

        We also don't have to worry about those proxies being reused when
        finding the token, since the token is found relatively quickly.

        >>> Not sure if using these callbacks versus just creating the tasks immediately
        >>> in the async func makes a huge difference, but we'll keep for now.
        """
        asyncio.create_task(proxy.add_error(e))

        proxy.just_used()
        asyncio.create_task(self.proxy_handler.pool.put(proxy))


class GetRequestHandler(RequestHandler):

    __method__ = 'GET'

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise TokenNotInResponse()
        return token


class PostRequestHandler(RequestHandler):

    __method__ = 'POST'

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    def _headers(self, token):
        headers = super(PostRequestHandler, self)._headers()
        headers[settings.TOKEN_HEADER] = token
        return headers

    async def _get_result_from_response(self, response, context):
        try:
            result = await response.json()
        except ValueError:
            raise ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result, context)

    async def _handle_client_response(self, response, context):
        """
        Takes the AIOHttp ClientResponse and tries to return a parsed
        InstagramResult object.

        For AIOHttp sessions and client responses, we cannot read the json
        after response.raise_for_status() has been called.

        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        if response.status >= 400 and response.status < 500:
            if response.status == 400:
                return await self._get_result_from_response(response, context)
            else:
                response.raise_for_status()
        else:
            return await self._get_result_from_response(response, context)

    async def _handle_parsed_result(self, result, context):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        if result.has_error:
            raise InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError("Inconslusive result.")
            return result
