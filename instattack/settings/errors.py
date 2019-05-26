import aiohttp
import ssl
from itertools import chain


"""
AioHTTP Client Exception Reference
----------------------------------
https://docs.aiohttp.org/en/stable/client_reference.html

-- ClientError

    -- ClientResponseError(ClientError): These exceptions could happen after we
            get response from server.

    -- ClientConnectionError(ClientError): These exceptions related to low-level
            connection problems.

        : Connection reset by peer

        -- ServerConnectionError(ClientConnectionError)

                -- ServerDisconnectError(ServerConnectionError)
                -- ServerTimeoutError(ServerConnectionError, asyncio.TimeoutError)

        -- ClientOSError(ClientConnectionError, OSError): Subset of connection
                errors that are initiated by an OSError exception.

            : OSError: Too many open files

            -- ClientConnectorError(ClientOSError)

                -- ClientProxyConnectionError(ClientConnectorError)
                -- ClientSSLError(ClientConnectorError) -> Raise Exceptions Here

                    -- ClientConnectorCertificateError(ClientSSLError, ssl.SSLError)
                    -- ClientConnectorSSLError(ClientSSLError, ssl.CertificateError)

                        :[SSL: WRONG_VERSION_NUMBER] wrong version number
"""


REQUEST_ERRORS = (
    aiohttp.ClientProxyConnectionError,
    # Not sure why we need the .client_exceptions version and the base version?
    aiohttp.client_exceptions.ClientConnectorError,
    aiohttp.ServerConnectionError,
    # Not sure why we have to add these even though they should be
    # covered by their parents...
    aiohttp.ClientConnectorError,
    aiohttp.ClientConnectorCertificateError,
    aiohttp.ClientConnectorSSLError,
    aiohttp.ClientHttpProxyError,
    ConnectionResetError,
    ConnectionRefusedError,
    ssl.SSLError,
    TimeoutError,
)


ERROR_CLASSIFICATION = {
    'client_connection': (
        'ClientConnectorError',
        'ClientConnectorError',
    ),
    'proxy_connection': (
        'ClientProxyConnectionError',
        'ClientHttpProxyError',
    ),
    'server_connection': (
        'ConnectionResetError',
        'ConnectionRefusedError',
        'ServerConnectionError',
        'ServerDisconnectedError',
    ),
    'ssl': (
        'SSLError',
        'ClientConnectorCertificateError',
        'ClientConnectorSSLError',
    ),
    # We shouldn't have to worry about non-classified ClientResponseError(s) since
    # they will always be raised as exceptions.
    'invalid_response': (
        'InvalidResponseJson',
        'InstagramResultError',
    ),
    'too_many_requests': (
        'ClientTooManyRequests',
    ),
    'timeout': (
        'TimeoutError',
    )
}

# Mapping of Error to Classification
# i.e. {'ClientTooManyRequests': 'too_many_requests'...}
ERROR_TRANSLATION = dict(chain.from_iterable(
    zip(item[0], [item[1] for i in range(len(item[0]))])
    for item in [(k, vi) for vi, k in ERROR_CLASSIFICATION.items()]
))


ERROR_TYPE_CLASSIFICATION = {
    'connection': (
        'client_connection',
        'proxy_connection',
        'server_connection',
        'timeout',
    ),
    'ssl': (
        'ssl',
    ),
    'response': (
        'invalid_response',
        'too_many_requests',
    )
}

ERROR_TYPE_TRANSLATION = dict(chain.from_iterable(
    zip(item[0], [item[1] for i in range(len(item[0]))])
    for item in [(k, vi) for vi, k in ERROR_TYPE_CLASSIFICATION.items()]
))

ERROR_TREATMENT = {
    # Fatal Error:  If `remove_invalid_proxy` is set to True and this error occurs,
    # the proxy will be removed from the database.  If `remove_invalid_proxy` is
    # False, the proxy will just be noted with the error and the proxy will not
    # be put back in the pool.
    'fatal': (

    ),
    # Semi-Fatal Error: Regardless of the value of `remove_invalid_proxy`, the
    # proxy will be noted with the error and the proxy will be removed from the
    # pool.
    'semifatal': (
        'InvalidResponseJson',
        'InstagramResultError',
        'ConnectionResetError',
        'ConnectionRefusedError',
        'ServerConnectionError',
        'ServerDisconnectedError',
        'ClientProxyConnectionError',
        'ClientConnectorError',
        'ClientConnectorError',
        'ClientHttpProxyError',
        'TimeoutError',
    ),
    # General Error: Proxy will be noted with error but put back in the pool.
    'error': (
        # We will check the number of requests for proxy if this occurs before pulling from pool.
        'ClientTooManyRequests',
        'SSLError',
        'ClientConnectorCertificateError',
        'ClientConnectorSSLError',
    ),
    # Inconclusive Error:  Proxy will not be noted with the error and the
    # proxy will be put back in pool.
    'inconclusive': (

    )
}

ERROR_TREATMENT_TRANSLATION = dict(chain.from_iterable(
    zip(item[0], [item[1] for i in range(len(item[0]))])
    for item in [(k, vi) for vi, k in ERROR_TREATMENT.items()]
))
