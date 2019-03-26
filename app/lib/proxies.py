from __future__ import absolute_import

import app.settings as settings


__all__ = ('BadProxies', )


class BadProxies(object):

    def __init__(self):
        self.proxies = []

    def __contains__(self, proxy):
        for _proxy in self.proxies:
            if _proxy.ip == proxy.ip and _proxy.port == proxy.port:
                return True
        return False

    def append(self, proxy):
        if len(self.proxies) >= settings.MAX_BAD_PROXIES:
            self.proxies.pop(0)
        self.proxies.append(proxy)
