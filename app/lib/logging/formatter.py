from __future__ import absolute_import

import aiohttp

from formats import RecordAttributes, LoggingLevels

from app.lib.utils import array_string


def get_exception_status_code(exc, formatted=False):

    if isinstance(exc, aiohttp.ClientError):
        if formatted:
            return RecordAttributes.STATUS_CODE.format(exc.status)
        return exc.status
    else:
        return None


def get_exception_request_method(exc, formatted=False):

    if isinstance(exc, aiohttp.ClientError):
        if exc.request_info.method:
            if formatted:
                return RecordAttributes.METHOD.format(exc.request_info.method)
            return exc.request_info.method
    return None


def get_exception_message(exc, level, formatted=False):
    if isinstance(level, str):
        level = LoggingLevels[level]

    if isinstance(exc, aiohttp.ClientError):
        message = getattr(exc, 'message', None) or exc.__class__.__name__
        if formatted:
            return level.format_message(message)
        return message

    # Although these are the same for now, we might want to treat our exceptions
    # differently in the future.
    # Maybe return str(exc) if the string length isn't insanely long.
    message = getattr(exc, 'message', None) or str(exc)
    if formatted:
        return level.format_message(message)
    return message


def format_exception_message(exc, level):
    return array_string(
        get_exception_request_method(exc, formatted=True),
        get_exception_message(exc, level, formatted=True),
        get_exception_status_code(exc, formatted=True)
    )


def format_log_message(msg, level):
    if isinstance(msg, Exception):
        return format_exception_message(msg, level)
    else:
        msg = level.format_message(msg)
        return RecordAttributes.MESSAGE.format(msg)


class LogItem(str):

    def __new__(cls, item, prefix=None, suffix=None, formatter=None, indent=0):
        cls.indent = indent

        prefix = prefix or ""
        suffix = suffix or ""
        indentation = " " * cls.indent

        if formatter:
            item = formatter.format(item)

        item = "%s%s%s" % (prefix, item, suffix)
        item = "%s%s" % (indentation, item)
        return str.__new__(cls, item)


class LogFormattedLine(LogItem):

    def __new__(cls, *items, indent=0):
        content = LogItem(" ".join(items), indent=indent)
        return str.__new__(cls, "\n %s \n" % content)


class LogFormattedString(str):

    def __new__(cls, *items):
        lines = []
        current_indentation = 0

        for i, item in enumerate(items):
            indentation = " " * current_indentation

            if isinstance(item, LogFormattedLine):
                current_indentation = item.indent
                lines.append(item)
            else:
                indentation = " " * current_indentation
                item = "%s%s" % (indentation, item)

                if len(lines) != 0:
                    if isinstance(lines[-1], LogFormattedLine):
                        lines.append(item)
                    else:
                        lines[-1] = ' '.join([lines[-1], item])
                else:
                    lines.append(item)

        return str.__new__(cls, " ".join(lines))
