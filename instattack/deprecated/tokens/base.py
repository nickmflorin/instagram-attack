import aiohttp

from instattack.exceptions import ClientResponseError
from instattack.core.base import RequestHandler

from .exceptions import TokenNotInResponse


class GetRequestHandler(RequestHandler):

    __method__ = 'GET'

    async def handle_client_response(self, response):
        """
        Takes the AIOHttp ClientResponse and tries to return a parsed
        InstagramResult object.

        For AIOHttp sessions and client responses, we cannot read the json
        after response.raise_for_status() has been called.

        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            raise ClientResponseError(response)
        else:
            if response.cookies:
                cookie = response.cookies.get('csrftoken')
                if cookie:
                    return cookie.value
            raise TokenNotInResponse(response)
