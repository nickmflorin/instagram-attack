import asyncio

from instattack.app.proxies import ProxyTrainPool

from .base import RequestHandler, ProxyHandler


__all__ = (
    'ProxyTrainHandler',
    'TrainHandler',
)


class ProxyTrainHandler(ProxyHandler):

    __name__ = "Proxy Attack Handler"

    def __init__(self, loop, **kwargs):
        super(ProxyTrainHandler, self).__init__(loop, **kwargs)
        self.pool = ProxyTrainPool(loop, self.broker, start_event=self.start_event)


class TrainHandler(RequestHandler):

    __name__ = 'Train Handler'
