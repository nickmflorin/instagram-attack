from __future__ import absolute_import

import queue
import threading

import app.settings as settings

from app.exceptions import InstagramTooManyRequests
from app.lib.api import ProxyApi, InstagramApi


class BrowserThread(threading.Thread):

    def __init__(self, user, passwords_queue, proxy_queue, results_queue):
        super(BrowserThread, self).__init__()

        self.user = user
        self.passwords_queue = passwords_queue
        self.proxy_queue = proxy_queue
        self.results_queue = results_queue

        self.stop_request = threading.Event()

    def run(self):
        while not self.stop_request.isSet():
            try:
                proxy = self.proxy_queue.get(True, 0.05)
            except queue.Empty:
                print("No proxies")
                continue
            else:
                api = InstagramApi(self.user.username, proxy)
                try:
                    results = api.login('Whispering1')
                except InstagramTooManyRequests as e:
                    print("TOO MAMY REQUESTS")
                else:
                    self.results_queue.put(results)
            # try:
            #     password = self.passwords_queue.get(True, 0.05)
            # except queue.Empty:
            #     print("No passwords")
            #     continue
            # else:
            #     print(f"Got password {password} from queue")
            # try:
            #     proxy = self.proxy_queue.get(True, 0.05)
            # except queue.Empty:
            #     print("No proxies")
            # else:
            #     print(f"Got proxy {proxy} from queue.")
                # We are not going to want to reget the token for each request
                # api = InstagramApi(proxy)
                # token = api.get_token()
                # api.update_headers(token=token)
                # results = api.login('nickmflorin', password)
                # print('Got Results')
                # self.results_queue.put(results)

    def join(self, timeout=None):
        print("Setting BrowserThread stop request.")
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
        print("Setting ProxyThread stop request.")
        self.stop_request.set()
        super(ProxyThread, self).join(timeout)
