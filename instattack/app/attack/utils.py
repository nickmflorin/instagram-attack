import re

from instattack import settings


async def get_token(session):
    """
    IMPORTANT:
    ---------
    The only reason to potentially use async retrieval of token would be if we
    wanted to use proxies and weren't sure how well the proxies would work.  It
    is much faster to just use a regular request, but does not protect identity.

    For now, we will go the faster route, but leave the code around that found
    the token through iterative async requests for the token.
    """
    async with session.get(settings.INSTAGRAM_URL) as response:
        text = await response.text()
        token = re.search('(?<="csrf_token":")\w+', text).group(0)
        return token, response.cookies
