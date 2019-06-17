import asyncio
from cement import ex
import functools

from termx.terminal import Cursor


def proxy_command(help=None, limit=None, arguments=None):

    arguments = arguments or []
    if limit:
        arguments = [(['-l', '--limit'],
            {'help': 'Limit the Number of Proxies', 'type': int})] + arguments

    def proxy_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()

            Cursor.newline()
            return func(instance, *args, **kwargs)

        return ex(help=help, arguments=arguments)(wrapped)

    return proxy_command_wrapper


def user_command(help=None, arguments=None):
    arguments = arguments or []
    arguments = [(['username'], {'help': 'Username'})] + arguments

    def user_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()
            new_args = (instance.app.pargs.username, ) + args

            Cursor.newline()
            return func(instance, *new_args, **kwargs)

        return ex(help=help, arguments=arguments)(wrapped)

    return user_command_wrapper


def existing_user_command(help=None, arguments=None):
    arguments = arguments or []
    arguments = [(['username'], {'help': 'Username'})] + arguments

    def user_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()

            user = instance.get_user()
            setattr(instance.loop, 'user', user)

            new_args = (user, ) + args

            Cursor.newline()
            return func(instance, *new_args, **kwargs)

        return ex(help=help, arguments=arguments)(wrapped)

    return user_command_wrapper
