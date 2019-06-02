import asyncio
from cement import ex
import functools


def command(help=None, arguments=[]):
    return ex(help=help, arguments=arguments)


def proxy_command(help=None, limit=None):
    arguments = [(
        ['-c', '--concurrent'], {'help': 'Save or Update Proxies Concurrently'}
    )]
    if limit:
        arguments.append((
            ['-l', '--limit'], {'help': 'Limit the Number of Proxies'}
        ))

    return command(help=help, arguments=arguments)


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


def existing_user_command(help=None):

    def user_command_wrapper(func):

        @functools.wraps(func)
        def wrapped(instance, *args, **kwargs):
            instance.loop = asyncio.get_event_loop()

            user = instance.get_user()
            new_args = (user, ) + args
            return func(instance, *new_args, **kwargs)

        arguments = [
            (['username'], {'help': 'Username'}),
        ]

        return ex(help=help, arguments=arguments)(wrapped)

    return user_command_wrapper
