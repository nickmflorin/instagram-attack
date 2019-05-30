import aiohttp
import concurrent.futures
import ssl

from .http_exceptions import InstagramResultError


SEVER_CONNECTION_ERRORS = (
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ServerConnectionError,
    aiohttp.ServerDisconnectedError,
    ConnectionResetError,
    ConnectionRefusedError,

)

CLIENT_CONNECTION_ERRORS = (
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ClientConnectorError,
    aiohttp.ClientOSError,
    aiohttp.client_exceptions.ClientConnectorError,
    aiohttp.client_exceptions.ClientOSError,

)

PROXY_CONNECTION_ERRORS = (
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ClientProxyConnectionError,
)

SSL_ERRORS = (
    aiohttp.ClientConnectorCertificateError,
    aiohttp.ClientConnectorSSLError,
    ssl.SSLError,  # Just for Peace of Mind

)

TIMEOUT_ERRORS = (
    TimeoutError,
    concurrent.futures._base.TimeoutError,
)

HTTP_REQUEST_ERRORS = (
    SEVER_CONNECTION_ERRORS +
    CLIENT_CONNECTION_ERRORS +
    PROXY_CONNECTION_ERRORS +
    SSL_ERRORS +
    TIMEOUT_ERRORS
)

RESPONSE_FORMAT_ERRORS = (
    ValueError,
    aiohttp.client_exceptions.ContentTypeError,
    aiohttp.ContentTypeError,
)

PROXY_CLIENT_ERRORS = (
    aiohttp.ClientHttpProxyError,
)

GENERAL_RESPONSE_ERRORS = (
    aiohttp.ClientResponseError,
)

CUSTOM_RESPONSE_ERRORS = (
    InstagramResultError,
)

HTTP_RESPONSE_ERRORS = (
    RESPONSE_FORMAT_ERRORS +
    GENERAL_RESPONSE_ERRORS +
    CUSTOM_RESPONSE_ERRORS +
    PROXY_CLIENT_ERRORS
)
