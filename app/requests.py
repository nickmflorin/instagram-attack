from __future__ import absolute_import

import random
import asyncio
import traceback

from app import settings

"""
TODO
-----
Introduce timeout here if we cannot retrieve the token - if there is a connection
error we might not retrieve a token for any of the proxies.

We might want to try to refresh proxies after they are retrieved from
the queue if the request is successful.

NOTES
------
We can use the following url to make sure that requests are using the proxy
correctly:
future = session.get('https://api.ipify.org?format=json')
"""


class request_handler(object):

    def __init__(self, config, global_stop_event, queues):
        self.config = config
        self.global_stop_event = global_stop_event
        self.user_agent = random.choice(settings.USER_AGENTS)
        self.stop_event = asyncio.Event()
        self.queues = queues

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    def log_request(self, context, log, retry=1, method="GET"):
        stack = traceback.extract_stack()
        line_no = stack[-3].lineno
        file_name = stack[-3].filename

        if retry == 1:
            log.info(
                f'Sending {method.upper()} Request',
                extra=self._log_context(context, line_no=line_no, file_name=file_name)
            )
        else:
            log.info(
                f'Sending {method.upper()} Request, Attempt {retry}',
                extra=self._log_context(context, line_no=line_no, file_name=file_name)
            )

    def log_post_request(self, context, log, retry=1):
        self.log_request(context, log, retry=1, method='POST')

    def log_get_request(self, context, log, retry=1):
        self.log_request(context, log, retry=1, method='GET')
