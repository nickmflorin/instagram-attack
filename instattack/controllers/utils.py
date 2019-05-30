from cement import ex


def command(help=None, arguments=[]):
    return ex(help=help, arguments=arguments)


def username_command(help=None, arguments=None):
    _arguments = [(['username'], {'help': 'Username'})]
    arguments = arguments or []
    _arguments.extend(arguments)

    return command(help=help, arguments=arguments)


def proxy_command(help=None, limit=None):
    arguments = [(
        ['-c', '--concurrent'], {'help': 'Save or Update Proxies Concurrently'}
    )]
    if limit:
        arguments.append((
            ['-l', '--limit'], {'help': 'Limit the Number of Proxies'}
        ))

    return command(help=help, arguments=arguments)
