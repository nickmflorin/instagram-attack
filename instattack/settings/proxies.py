PROXY_COUNTRIES = []
PROXY_TYPES = ["HTTP"]

PROXY_BROKER_ERROR_TRANSLATION = {
    'connection_error': 'client_connection',
}

PROXY_PRIORITY_FIELDS = (
    (-1, 'num_active_successful_requests'),
    (-1, 'num_successful_requests'),
    (-1, 'active_error_count'),
    (-1, 'error_count'),
    (1, 'avg_resp_time'),
)

PROXY_FORMAL_ATTRS = {
    'num_active_requests': 'Num. Active Requests',
    'flattened_error_rate': 'Flat. Error Rate',
    'avg_resp_time': 'Avg. Response Time',
    'time_since_used': 'Time Since Used',
    'num_connection_errors': 'Num. Connection Errors',
    'num_invalid_response_errors': 'Num. Invalid Response Errors',
    'num_ssl_errors': 'Num. SSL Connection Errors',
    'num_instagram_errors': 'Num. Instagram Identified Errors',
    'num_too_many_requests_errors': 'Num. Too Many Request Errors',
    'num_active_too_many_requests_errors': 'Num. Active Too Many Request Errors',
    'error_count': 'Number of Total Errors',
    'active_error_count': 'Number of Total Active Errors',
}
