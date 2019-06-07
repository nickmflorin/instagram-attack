import asyncio
from datetime import datetime
import pytest

from instattack.app.proxies import ConfirmedQueue, SimpleProxyPool
from instattack.app.models.proxies import Proxy

from .main import InstattackTest


TEST_PROXIES = []
# TEST_PROXIES = [
#     Proxy(
#         host="0.0.0.0",
#         port=1080,
#         history=[],
#         avg_resp_time=3.1,
#         date_added=datetime(2018, 1, 1)
#     ),
#     Proxy(
#         host="0.0.0.1",
#         port=1080,
#         history=[],
#         avg_resp_time=3.1,
#         date_added=datetime(2018, 1, 1)
#     ),
#     Proxy(
#         host="0.0.0.2",
#         port=1080,
#         history=[],
#         avg_resp_time=3.1,
#         date_added=datetime(2018, 1, 1)
#     ),
# ]


@pytest.mark.asyncio
async def test_confirmed_queue(event_loop):
    """
    TODO:
    ----
    Make a test configuration file and load that.
    """
    async with InstattackTest():

        pool = SimpleProxyPool(event_loop)

        lock = asyncio.Lock()
        queue = ConfirmedQueue(pool, lock)

        for proxy in TEST_PROXIES:
            queue.put(proxy)
