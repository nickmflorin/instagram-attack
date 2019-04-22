from __future__ import absolute_import

from itertools import islice
import subprocess

import asyncio


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


def get_pids_from_terminal_content(content, port, limit=None):
    lines = content.split('\n')
    if len(lines) < 2:
        raise IOError(f"Invalid content returned from lsof -i:{port}")

    lines = lines[1:]
    if limit:
        lines = lines[:limit]

    rows = [
        [item for item in line.split(' ') if item.strip() != '']
        for line in lines
    ]

    if limit == 1:
        return int(rows[0][1])

    pids = []
    for row in rows:
        try:
            pids.append(row[1])
        except IndexError:
            continue
    return [int(pid) for pid in pids]


def find_pids_on_port(port):
    try:
        content = subprocess.check_output(['lsof', '-i', ':%s' % port], universal_newlines=True)
    except subprocess.CalledProcessError:
        return []
    else:
        pids = get_pids_from_terminal_content(content, port)
        return list(set(pids))
