from .server import LoginBroker, TokenBroker

BROKERS = {
    'GET': TokenBroker,
    'POST': LoginBroker,
}
