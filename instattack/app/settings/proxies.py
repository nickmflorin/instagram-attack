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
    'instagram': (
        'invalid_instagram_result',
    ),
    'invalid_response': (
        'invalid_response_json',
        'invalid_response',
        'proxy_auth',
    ),
    'too_many_requests': (
        'too_many_requests',
    ),
}
