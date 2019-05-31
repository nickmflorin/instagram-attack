import asyncio
from datetime import datetime

from instattack.app.proxies.broker import ProxyBroker
from instattack.app.proxies.pool import ProxyPool
from instattack.app.proxies.models import Proxy

from instattack.main import InstattackTest


ERRORS = {
    'all': {
        'connection': 2,
        'response': 1,
        'instagram': 0,
        'ssl': 4,
    },
    'most_recent': 'response',
}

ACTIVE_ERRORS = {
    'all': {
        'connection': 1,
        'response': 1,
        'instagram': 0,
    },
    'most_recent': 'response',
}

TEST_PROXIES = [
    Proxy(
        host="0.0.0.0",
        port=1080,
        errors=ERRORS,
        active_errors=ACTIVE_ERRORS,
        num_requests=9,
        num_active_requests=3,
        avg_resp_time=3.1,
        date_added=datetime(2018, 1, 1)
    ),
    Proxy(
        host="0.0.0.1",
        port=1080,
        errors=ERRORS,
        active_errors=ACTIVE_ERRORS,
        num_requests=9,
        num_active_requests=3,
        avg_resp_time=3.1,
        date_added=datetime(2018, 1, 1)
    ),
    Proxy(
        host="0.0.0.2",
        port=1080,
        errors=ERRORS,
        active_errors=ACTIVE_ERRORS,
        num_requests=9,
        num_active_requests=3,
        avg_resp_time=3.1,
        date_added=datetime(2018, 1, 1)
    ),
]


def test_num_requests():

    proxy = Proxy(
        host="0.0.0.0",
        port=1080,
        errors=ERRORS,
        active_errors=ACTIVE_ERRORS,
        num_requests=9,
        num_active_requests=3,
        avg_resp_time=3.1,
        date_added=datetime(2018, 1, 1)
    )

    assert proxy._num_requests(active=False, success=True) == 2
    assert proxy._num_requests(active=True, success=True) == 1
    assert proxy._num_requests(active=False, success=False) == 7
    assert proxy._num_requests(active=True, success=False) == 2


def test_num_errors():

    proxy = Proxy(
        host="0.0.0.0",
        port=1080,
        errors=ERRORS,
        active_errors=ACTIVE_ERRORS,
        num_requests=9,
        num_active_requests=3,
        avg_resp_time=3.1,
        date_added=datetime(2018, 1, 1)
    )

    assert proxy._num_errors('instagram', active=False) == 0
    assert proxy._num_errors('ssl', active=False) == 4
    assert proxy._num_errors('ssl', active=True) == 0
    assert proxy._num_errors('connection', active=False) == 2
    assert proxy._num_errors('connection', active=True) == 1
    assert proxy._num_errors(active=True) == 2
    assert proxy._num_errors(active=False) == 7


def test_pool():
    argv = ['attack']
    with InstattackTest(argv=argv) as app:
        import ipdb; ipdb.set_trace()
        async def _test_pool(loop):

            broker = ProxyBroker(app.config['instattack'], limit=None)
            pool = ProxyPool(app.config, broker, start_event=asyncio.Event())
            pool.hold.extend(TEST_PROXIES)
            proxy = pool._get_from_hold()
            import ipdb; ipdb.set_trace()


        loop = asyncio.get_event_loop()
        loop.run_until_complete(_test_pool(loop))
