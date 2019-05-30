from datetime import datetime

from instattack.app.proxies.models import Proxy

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
