from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.config import config

from instattack.lib.utils import (
    percentage, limit_as_completed, start_and_stop, break_before)

from instattack.app.exceptions import (
    NoPasswordsError, find_request_error, find_response_error)

from instattack.app.mixins import LoggerMixin
from instattack.app.proxies import ProxyBroker, ProxyAttackPool, ProxyTrainPool

from .models import InstagramResults
from .utils import get_token
from .login import attempt


"""
In Regard to Cancelled Tasks on Web Server Disconnect:
---------
<https://github.com/aio-libs/aiohttp/issues/2098>

Now web-handler task is cancelled on client disconnection (normal socket closing
by peer or just connection dropping by unpluging a wire etc.)

This is pretty normal behavior but it confuses people who come from world of
synchronous WSGI web frameworks like flask or django.

>>> async def handler(request):
>>>     async with request.app['db'] as conn:
>>>          await conn.execute('UPDATE ...')

The above is problematic if there is a client disconnect.

To remedy:

(1)  For client disconnections/fighting against Task cancellation I would
     recommend asyncio.shield. That's why it exists
(2)  In case user wants a way to control tasks in a more granular way, then I
     would recommend aiojobs
(3)  Ofc if user wants to execute background tasks (inside the same loop) I
      would also recommend aiojobs
"""



class TrainHandler(RequestHandler):

    __name__ = 'Train Handler'


