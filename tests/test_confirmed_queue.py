import asyncio
from datetime import datetime
import pytest

from instattack.app.proxies import ConfirmedQueue, SimpleProxyPool
from instattack.app.models.proxies import Proxy

from .main import InstattackTest


@pytest.mark.asyncio
async def test_confirmed_queue(event_loop):
    """
    TODO:
    ----
    Make a test configuration file and load that.

    Make a configuration for database and make sure tortoise is using that config,
    figure out how to do unit testing with Tortoise ORM.

    See if there is a fixture we can make so that all of our test cases can be
    wrapped in:
    >>> async with InstattackTest() as app
    """
    async with InstattackTest():

        TEST_PROXIES = [
            Proxy(
                host="0.0.0.0",
                port=1080,
                history=[
                    {
                        "date": "06/04/2019, 14:35:33",
                        "error": "proxy_connection"
                    },
                    {
                        "date": "06/04/2019, 14:35:45",
                        "error": "proxy_connection"
                    },
                    {
                        "date": "06/04/2019, 14:37:30",
                    },
                    {
                        "date": "06/04/2019, 15:18:07",
                    }
                ],
                avg_resp_time=3.1,
                date_added=datetime(2018, 1, 1)
            ),
            Proxy(
                host="0.0.0.1",
                port=1080,
                history=[
                    {
                        "date": "06/04/2019, 14:35:33",
                        "error": "proxy_connection"
                    },
                    {
                        "date": "06/04/2019, 14:35:45",
                        "error": "proxy_connection"
                    },
                    {
                        "date": "06/04/2019, 14:37:30",
                    },
                    {
                        "date": "06/04/2019, 15:18:07",
                    }
                ],
                avg_resp_time=3.1,
                date_added=datetime(2018, 1, 1)
            ),
            Proxy(
                host="0.0.0.2",
                port=1080,
                history=[
                    {
                        "date": "06/04/2019, 14:35:33",
                        "error": "proxy_connection"
                    },
                    {
                        "date": "06/04/2019, 14:35:45",
                        "error": "proxy_connection"
                    },
                    {
                        "date": "06/04/2019, 14:37:30",
                    },
                    {
                        "date": "06/04/2019, 15:18:07",
                    }
                ],
                avg_resp_time=3.1,
                date_added=datetime(2018, 1, 1)
            ),
        ]

        pool = SimpleProxyPool(event_loop)

        lock = asyncio.Lock()
        queue = ConfirmedQueue(pool, lock)

        for proxy in TEST_PROXIES:
            proxy.save()

        for proxy in TEST_PROXIES:
            print(proxy.id)
            # await queue.put(proxy)

        first = await queue.get()
