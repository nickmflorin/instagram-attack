from instattack.app.proxies import SimpleProxyPool

from .proxies import SimpleProxyHandler
from .base import AbstractRequestHandler


__all__ = (
    'TrainHandler',
)


class TrainHandler(AbstractRequestHandler):

    __name__ = 'Train Handler'
    __proxy_handler__ = SimpleProxyHandler
    __proxy_pool__ = SimpleProxyPool
