import asyncio
from cement import ex
import functools

LEVEL_ARGUMENT = (
    ['-lv', '--level'],
    {
        'action': 'store',
        'help': 'Override the Logging Level'
    }
)


def proxy_command(help=None, limit=None, arguments=None):

    arguments = arguments or []
    arguments.append(LEVEL_ARGUMENT)

    if limit:
        arguments.append((
            ['-l', '--limit'], {'help': 'Limit the Number of Proxies', 'type': int},
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
            LEVEL_ARGUMENT
        ]

        return ex(help=help, arguments=arguments)(wrapped)

    return user_command_wrapper


def existing_user_command(help=None, arguments=None):
    new_arguments = arguments or []
    new_arguments.append(LEVEL_ARGUMENT)

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
