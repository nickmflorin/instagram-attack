from __future__ import absolute_import

import logbook

from .formatter import LOGIN_ATTEMPT_FORMAT, TOKEN_TASK_FORMAT


__all__ = ('login_attempt_log', 'token_task_log', )


# log = logbook.Logger('Main')

# logger_group = logbook.LoggerGroup()
# logger_group.level = logbook.WARNING

# log1 = logbook.Logger('First')
# log2 = logbook.Logger('Second')

# logger_group.add_logger(log1)
# logger_group.add_logger(log2)


def token_task_log(func):
    def wrapper(*args, **kwargs):
        handler = logbook.StderrHandler()
        handler.format_string = TOKEN_TASK_FORMAT
        with handler.threadbound():
            return func(*args, **kwargs)
    return wrapper


def login_attempt_log(func):
    def wrapper(*args, **kwargs):
        handler = logbook.StderrHandler()
        handler.format_string = LOGIN_ATTEMPT_FORMAT
        with handler.threadbound():
            return func(*args, **kwargs)
    return wrapper


token_task_log.logger = logbook.Logger('Token Fetch')
token_task_log.logger.level = logbook.INFO

login_attempt_log.logger = logbook.Logger('Login Attempt')
