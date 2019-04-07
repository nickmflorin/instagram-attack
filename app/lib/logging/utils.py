from __future__ import absolute_import

from app.lib import exceptions

from .constants import LoggingLevels, RecordAttributes, Styles


class RecordWrapper(object):

    def __init__(self, record):
        self.record = record

    def __getattr__(self, key):
        if key == 'levelname' and self.isSuccess:
            return 'SUCCESS'
        return getattr(self.record, key, None)

    def _msg(self, formatted=False):
        if formatted:
            return LoggingLevels[self.levelname].format_message(self.msg)
        return self.msg

    def _task(self, formatted=False):
        if not self.task:
            return None

        task = None
        if isinstance(self.task, str):
            task = self.task
        elif hasattr(self.task, 'name'):
            task = self.task.name
        else:
            raise exceptions.FatalException('Invalid task supplied to logger.')

        if task and formatted:
            return RecordAttributes.TASK.format(task)

    def _traceback(self, formatted=False):
        # See note in AppLogger.makeRecord()
        # If line_no and file_name not explicitly provided, or we are not in
        # DEBUG, CRITICAL or ERROR levels, don't include in message.
        if (
            not (self.line_no and self.file_name) and
                self.levelname not in ('ERROR', 'CRITICAL', 'DEBUG')
        ):
            return None

        lineno = self.line_no or self.lineno
        filename = self.file_name or self.filename
        if lineno and filename:
            if formatted:
                return f"({filename}, {Styles.BOLD.encode(lineno)})"
            return f"{filename}, {lineno}"

    def _proxy(self, formatted=False):
        proxy = None
        if self.proxy:
            if isinstance(self.proxy, str):
                proxy = self.proxy
            else:
                proxy = f"{self.proxy.host}:{self.proxy.port}"
        if proxy and formatted:
            return RecordAttributes.PROXY.format(proxy)
        return proxy

    def _threadName(self, formatted=False):
        if not formatted:
            return self.threadName
        if self.threadName:
            return RecordAttributes.THREADNAME.format(self.threadName)
        return None

    def _name(self, formatted=False):
        if not formatted:
            return self.name
        if self.name:
            return RecordAttributes.NAME.format(self.name)
        return None

    def _token(self, formatted=False):
        if not formatted:
            return self.token
        if self.token:
            return RecordAttributes.TOKEN.format(self.token)
        return None

    def _levelname(self, formatted=False):
        if not formatted:
            return self.levelname
        return LoggingLevels[self.levelname].format(self.levelname)

    def _url(self, formatted=False):
        url = self.url
        if self.response:
            url = url or getattr(self.response, 'url', None)
        if url and formatted:
            return RecordAttributes.URL.format(url)
        return url

    def _status_code(self, formatted=False):
        status_code = self.status_code
        if self.response:
            status_code = status_code or (
                getattr(self.response, 'status_code', None) or
                getattr(self.response, 'status', None)
            )
        if status_code and formatted:
            return RecordAttributes.STATUS_CODE.format(status_code)
        return status_code
