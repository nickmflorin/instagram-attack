from __future__ import absolute_import

import asyncio
from collections import Iterable
from itertools import islice


def ensure_iterable(arg):
    if isinstance(arg, str):
        return [arg]
    elif not isinstance(arg, Iterable):
        return [arg]
    return arg


def array(*values):
    return [val for val in values if val is not None]


def array_string(*values, separator=" "):
    values = array(*values)
    return separator.join(values)


def get_token_from_cookies(cookies):
    # aiohttp ClientResponse cookies have .value attribute.
    cookie = cookies.get('csrftoken')
    if cookie:
        return cookie.value


def get_cookies_from_response(response):
    return response.cookies


def get_token_from_response(response):
    cookies = get_cookies_from_response(response)
    if cookies:
        return get_token_from_cookies(cookies)


def limited_as_completed(coros, limit):
    """
    Equivalent of asyncio.as_completed(tasks) except that it limits the number
    of concurrent tasks at any given time, and when that number falls below
    the limit it adds tasks back into the pool.
    """
    futures = [
        asyncio.ensure_future(c)
        for c in islice(coros, 0, limit)
    ]

    async def first_to_finish():
        while True:
            await asyncio.sleep(0)
            for f in futures:
                if f.done():
                    futures.remove(f)
                    try:
                        newf = next(coros)
                        futures.append(
                            asyncio.ensure_future(newf))
                    except StopIteration as e:
                        pass
                    return f.result()
    while len(futures) > 0:
        yield first_to_finish()


async def cancel_remaining_tasks(futures=None):
    if not futures:
        futures = asyncio.Task.all_tasks()

    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)
