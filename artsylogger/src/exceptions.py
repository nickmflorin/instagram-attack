class ArtsyLoggerException(Exception):

    def __str__(self):
        return self.__message__


class InvalidRecordCallable(ArtsyLoggerException):
    def __init__(self, func):
        if hasattr(func, '__name__'):
            self.__message__ = f"The callable {func.__name__} is invalid."
        else:
            self.__message__ = f"The callable {func} is invalid."
