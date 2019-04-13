from __future__ import absolute_import

from __future__ import absolute_import

import asyncio
import traceback


__all__ = ('TokenTaskContext', 'LoginTaskContext', 'LoginAttemptContext',
    'TaskManager', 'ProxyManager', 'PasswordManager', 'QueueManager')


class ProxyManager(object):

    def __init__(self, generated=None, good=None, handled=None):
        self.generated = generated or asyncio.Queue()
        self.good = good or asyncio.Queue()
        self.handled = handled or asyncio.Queue()

    async def get_best(self):
        # We could run into race conditions here - we may want to have a try
        # except.
        if not self.good.empty():
            return await self.good.get()
        return await self.handled.get()


class PasswordManager(object):

    def __init__(self, generated=None, attempted=None):
        self.generated = generated or asyncio.Queue()
        self.attempted = attempted or asyncio.Queue()


class QueueManager(object):

    def __init__(self, **kwargs):
        self.proxies = ProxyManager(**kwargs.get('proxies', {}))
        self.passwords = PasswordManager(**kwargs.get('passwords', {}))


class TaskContext(object):

    __name__ = None
    __attrs__ = ('index', )

    def __init__(self, **kwargs):
        for attr in self.__attrs__:
            if attr in kwargs:
                setattr(self, attr, kwargs.get(attr))
            elif kwargs.get('context'):
                super_context = kwargs['context']
                setattr(self, attr, getattr(super_context, attr))
        setattr(self, 'name', f'{self.__name__} {self.index}')

    def log_context(self, **kwargs):
        return {
            'task': self.name,
            **kwargs
        }


class TokenTaskContext(TaskContext):

    __name__ = 'Token Task'
    __attrs__ = TaskContext.__attrs__ + ('proxy', )


class LoginTaskContext(TaskContext):

    __name__ = 'Login Task'
    __attrs__ = TaskContext.__attrs__ + ('token', 'password', )

    def log_context(self, **kwargs):
        return super(LoginTaskContext, self).log_context(
            token=self.token,
            password=self.password,
            **kwargs,
        )


class LoginAttemptContext(LoginTaskContext):

    __name__ = 'Attempt'
    __attrs__ = LoginTaskContext.__attrs__ + ('proxy', )

    def __init__(self, context=None, **kwargs):
        super(LoginAttemptContext, self).__init__(context=context, **kwargs)
        self.name = f'{context.name} - {self.__name__} {self.index}'

    def log_context(self, **kwargs):
        return super(LoginTaskContext, self).log_context(
            proxy=self.proxy,
            **kwargs
        )


class TaskManager(object):

    def __init__(self, stop_event, log=None, tasks=None, limit=None):
        self.log = log
        self.stop_event = stop_event
        self.tasks = tasks or []
        self.limit = limit

    def upstream_traceback(self, tb):
        try:
            return traceback.extract_tb(tb)[-1]
        except AttributeError:
            return tb[-1]

    async def cancel_remaining_tasks(self, futures):
        tasks = [task for task in futures if task is not
             asyncio.tasks.Task.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        await asyncio.gather(*tasks, return_exceptions=True)

    def log_context(self, tb):
        """
        Providing to the log method as the value of `extra`.  We cannot get
        the actual stack trace lineno and filename to be overridden on the
        logRecord (see notes in AppLogger.makeRecord()) - so we provide custom
        values that will override if present.
        """
        upstream_tb = self.upstream_traceback(tb)
        return {
            'line_no': upstream_tb.lineno,
            'file_name': upstream_tb.filename,
        }

    def submit(self, task, context):

        task.__context__ = context
        self.add(task)

        extra = self.log_context(traceback.extract_stack())
        extra.update(**context.log_context())
        self.log.info("Submitting Task", extra=extra)

    def add(self, *tasks):
        for task in tasks:
            self.tasks.append(task)

    @property
    def index(self):
        return len(self.tasks)

    @property
    def active(self):
        if not self.limit:
            return not self.stop_event.is_set()
        return not self.stop_event.is_set() and len(self.tasks) < self.limit

    async def notify(self, message):
        if self.log:
            self.log.warning(message)

    async def stop(self):
        await self.notify('Setting Stop Event')
        self.stop_event.set()
        return await self._shutdown()

    async def _shutdown(self):
        if self.tasks:
            await self.notify("Cleaning up remaining tasks...")
            asyncio.ensure_future(self.cancel_remaining_tasks(self.tasks))
