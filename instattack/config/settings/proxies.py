PROXY_COUNTRIES = []
PROXY_TYPES = ["HTTP"]

PROXY_BROKER_ERROR_TRANSLATION = {
    'connection_error': 'client_connection',
}

# Used to Generalize Errors in Priority
# TODO: Make These More Granular
ERROR_TYPE_CLASSIFICATION = {
    'connection': (
        'client_connection',
        'proxy_connection',
        'server_connection',
    ),
    'timeout': (
        'timeout',
    ),
    'ssl': (
        'ssl',
    ),
    'client': {
        'proxy_auth',
        'proxy_client',
    },
    'instagram': (
        'invalid_instagram_result',
    ),
    'invalid_response': (
        'invalid_response_json',
        'invalid_response',
    ),
}

TIMEOUT_ERRORS = ('too_many_requests', 'too_many_open_connections')
