import aiofiles
import asyncio
from weakref import WeakKeyDictionary

from instattack import logger
from instattack import settings
from instattack.utils import task_is_third_party



async def coro_exc_wrapper(coro, loop):
    try:
        await coro
    except Exception as e:
        loop.call_exception_handler({'message': str(e), 'exception': e})


def get_remaining_tasks():
    tasks = asyncio.Task.all_tasks()
    return list(tasks)


async def cancel_remaining_tasks(futures=None, silence_exceptions=False, log_exceptions=None):
    log = logger.get_async(__name__, subname='cancel_remaining_tasks')

    if log_exceptions is None:
        log_exceptions = not silence_exceptions

    if not futures:
        log.debug('Collecting Default Tasks')
        futures = asyncio.Task.all_tasks()
        futures = [task for task in futures if task is not
            asyncio.tasks.Task.current_task()]

    def cancel_task(task):
        if not task.cancelled():
            if task.done():
                if task.exception():
                    # Need to find a more sustainable way of doing this, this makes
                    # sure that we are not raising exceptions for external tasks.
                    if not task_is_third_party(task):
                        if not silence_exceptions:
                            raise task.exception()
                        elif log_exceptions:
                            log.warning(task.exception())
            else:
                log.debug(f'Cancelling Task {task}')
                task.cancel()

    list(map(cancel_task, futures))
    await asyncio.gather(*futures, return_exceptions=True)
    return futures


def join(val, *gens):
    """
    Chains generators together where the values of the next generator are
    computed using the values of the first generator, and so on and so forth.

    Usage
    -----

    def gen1(val):
        for i in [1, 2]:
            yield "%s%s" % (val, i)

    def gen2(val):
        for i in ['a', 'b']:
            yield "%s%s" % (val, i)

    for ans in join('blue', gen1, gen2):
        print(ans)

    >>> bluea
    >>> bluea1
    >>> bluea2
    >>> blueb
    >>> blueb1
    >>> blueb2
    >>> blue1
    >>> blue2
    """
    for i, gen in enumerate(gens):

        def recursive_yield(index, value):
            if index < len(gens):
                if index == 0:
                    for element in gens[0](value):
                        yield element
                        yield from recursive_yield(1, element)
                else:
                    for element in gens[index](value):
                        yield element
                        yield from recursive_yield(index + 1, element)

        yield from recursive_yield(i, val)


def read_raw_data(filepath, limit=None):
    """
    Code Snippet
    ------------
    http://blog.mathieu-leplatre.info/some-python-3-asyncio-snippets.html

    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF.
            break
        yield line
    """
    from instattack.src.exceptions import InvalidFileLine

    count = 0

    lines = []
    with open(filepath) as f:
        for line in f.readlines():
            line = line.replace("\n", "")
            if line == "":
                exc = InvalidFileLine(i, val)  # noqa
                # log.error(exc) Don't Log Empty Lines for Now
            else:
                if not limit or count < limit:
                    lines.append(line)
                    count += 1
                else:
                    break
    return lines


async def stream_raw_data(filepath, limit=None):
    """
    Code Snippet
    ------------
    http://blog.mathieu-leplatre.info/some-python-3-asyncio-snippets.html

    reader = asyncio.StreamReader(loop=loop)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF.
            break
        yield line
    """
    from instattack.src.exceptions import InvalidFileLine

    count = 0
    async with aiofiles.open(filepath) as f:
        async for line in f:
            line = line.replace("\n", "")
            if line == "":
                exc = InvalidFileLine(i, val)  # noqa
                # log.error(exc) Don't Log Empty Lines for Now
            else:
                if not limit or count < limit:
                    yield line
                    count += 1
                else:
                    break


class DynamicProperty(object):
    """
    Base class for properties that provide basic configuration and control
    variables whose value might depend on how something is initialized or
    used.
    """
    default = None

    def __init__(self):
        self.data = WeakKeyDictionary()

    def __get__(self, instance, owner):

        if not self.data.get(instance):
            self.data[instance] = self._create_new(instance)
        return self.data[instance]

    def __set__(self, instance, value):
        raise ValueError('Cannot set this dynamic property.')


class Identifier(DynamicProperty):

    def _create_new(self, instance):
        """
        Creates the value of the property that will be assigned to the given
        instance.
        """
        value = None
        if hasattr(instance, '__name__'):
            value = instance.__name__
        else:
            value = instance.__class__.__name__
        return value
