PROXY_COUNTRIES = []
PROXY_TYPES = ["HTTP"]

PROXY_BROKER_ERROR_TRANSLATION = {
    'connection_error': 'client_connection',
}

PROXY_PRIORITY_FIELDS = (
    (-1, 'num_active_successful_requests'),
    (-1, 'num_successful_requests'),
    (1, 'num_connection_errors'),
    (1, 'num_response_errors'),
    (1, 'num_ssl_errors'),
    (1, 'avg_resp_time'),
)

PROXY_FORMAL_ATTRS = {
    'num_active_requests': 'Num. Active Requests',
    'flattened_error_rate': 'Flat. Error Rate',
    'avg_resp_time': 'Avg. Response Time',
    'time_since_used': 'Time Since Used',
    'num_connection_errors': 'Num. Connection Errors'
}
