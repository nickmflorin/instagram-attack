from __future__ import absolute_import

import asyncio

from .base import Handler


class ResultsHandler(Handler):

    __name__ = 'Results Handler'

    def __init__(self, **kwargs):
        super(ResultsHandler, self).__init__(**kwargs)
        self.attempts = asyncio.Queue()

    async def run(self, loop):
        """
        Stop event is not needed for the GET case, where we are finding a token,
        because we can trigger the generator to stop by putting None in the queue.
        On the other hand, if we notice that a result is authenticated, we need
        the stop event to stop handlers mid queue.
        """
        async with self.starting(loop):
            # When there are no more passwords, the Password Consumer will put
            # None in the results queue, triggering this loop to break and
            # the stop_event() to stop the Proxy Producer.
            index = 0
            while True:
                result = await self.queue.get()
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
                    self.stop_event.set()
                    break

                else:
                    self.log.error("Not Authenticated", extra={'password': result.context.password})
                    await self.attempts.put(result.context.password)

    async def stop(self, loop, save=True):
        async with self.stopping(loop):
            if save:
                await self.dump(loop)

    async def dump(self, loop):
        attempts_list = []
        self.log.notice('Dumping Password Attempts')
        while not self.attempts.empty():
            attempts_list.append(await self.attempts.get())
        self.user.update_password_attempts(attempts_list)
