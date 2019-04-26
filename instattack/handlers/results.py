from __future__ import absolute_import

import asyncio

from .base import Handler


class ResultsHandler(Handler):

    def __init__(self, user, results, **kwargs):
        super(ResultsHandler, self).__init__(**kwargs)

        self.user = user
        self.attempts = asyncio.Queue()
        self.results = results

    async def consume(self, loop, found_result_event):
        """
        Stop event is not needed for the GET case, where we are finding a token,
        because we can trigger the generator to stop by putting None in the queue.

        On the other hand, if we notice that a result is authenticated, we need
        the stop event to stop handlers mid queue.

        Since this consumer is at the bottom of the entire tree (i.e. only
        receiving information after all other consumers), we don't have to wait
        for a stop event in the loop, we can just break out of it.
        """
        index = 0
        with self.log.start_and_done('Consuming Results'):
            # When there are no more passwords, the Password Consumer will put
            # None in the results queue, triggering this loop to break and
            # the stop_event() to stop the Proxy Producer.

            # Note that we could add a stop event check here just to be safe
            # and guarantee it stops at the faster event (retrieval of None from
            # queue or stop event).
            while True:
                result = await self.results.get()

                if result is None:
                    # Triggered by Password Consumer
                    break

                index += 1

                # TODO: Cleanup how we are doing the percent complete operation,
                # maybe try to use progressbar package.
                self.log.notice("{0:.2%}".format(float(index) / self.user.num_passwords))
                self.log.notice(result)

                if result.authorized:
                    self.log.debug('Setting Stop Event')
                    # Notify the Password Consumer to stop - this will also stop
                    # the Proxy Producer.
                    found_result_event.set()
                    break

                else:
                    self.log.error("Not Authenticated", extra={'password': result.context.password})
                    await self.attempts.put(result.context.password)

    async def dump(self, loop):
        attempts_list = []

        with self.log.start_and_done('Dumping Attempts'):
            while not self.attempts.empty():
                attempts_list.append(await self.attempts.get())
            self.user.update_password_attempts(attempts_list)
