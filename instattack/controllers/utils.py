import asyncio
from cement import ex
import functools


def proxy_command(help=None, limit=None):

    arguments = [(
        ['-c', '--concurrent'],
        {'help': 'Save or Update Proxies Concurrently'}
    )]
    if limit:
        arguments.append((
            ['-l', '--limit'], {'help': 'Limit the Number of Proxies'}
        ))

    def proxy_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()
            return func(instance, *args, **kwargs)

        return ex(help=help, arguments=arguments)(wrapped)

    return proxy_command_wrapper


def user_command(help=None):

    def user_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()
            new_args = (instance.app.pargs.username, ) + args
            return func(instance, *new_args, **kwargs)

        arguments = [
            (['username'], {'help': 'Username'}),
        ]

        return ex(help=help, arguments=arguments)(wrapped)

    return user_command_wrapper


def existing_user_command(help=None, arguments=None):
    new_arguments = arguments or []

    def user_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()

            user = instance.get_user()
            setattr(instance.loop, 'user', user)

            new_args = (user, ) + args
            return func(instance, *new_args, **kwargs)

        arguments = [
            (['username'], {'help': 'Username'}),
        ] + new_arguments

        return ex(help=help, arguments=arguments)(wrapped)

    return user_command_wrapper
