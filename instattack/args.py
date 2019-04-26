from __future__ import absolute_import

from plumbum import cli


class ConfigConstant(object):
    def __init__(self, val):
        self.value = val


class ConfigArgs(object):

    def add_to_config(self, config, cls, name, val):
        prefix = None
        if hasattr(cls, '__prefix__'):
            prefix = getattr(cls, '__prefix__')

        second_prefix = None
        if hasattr(cls, '__second_prefix__'):
            second_prefix = getattr(cls, '__second_prefix__')

        if prefix:
            name = name.replace(f'{prefix}_', '')
        if second_prefix:
            name = name.replace(f'{second_prefix}_', '')
        config[name] = val

    def config_for_class(self, *cls_args):
        config = {}

        for _class_ in cls_args:
            for key, val in _class_.__dict__.items():
                if isinstance(val, ConfigConstant):
                    self.add_to_config(config, _class_, key, val.value)

            for name, switch in self.__dict__['_switches_by_name'].items():
                if switch.group == _class_.__group__:
                    self.add_to_config(config, _class_, name, getattr(self, name))
        return config


class TokenProxyBrokerArgs(ConfigArgs):

    __group__ = "Token Broker"
    __prefix__ = 'token'

    token_max_conn = cli.SwitchAttr(
        "--token_max_conn", int,
        default=100,
        group=__group__,
        help="The maximum number of concurrent checks of proxies."
    )
    token_max_tries = cli.SwitchAttr(
        "--token_max_tries", int,
        default=2,
        group=__group__,
        help="The maximum number of attempts to check a proxy."
    )

    token_verify_ssl = False


class TokenProxyServerArgs(ConfigArgs):

    __group__ = 'Token Proxy Server'
    __prefix__ = 'token'
    __second_prefix__ = 'proxy'

    # Not sure if it stops completely after this limit?  Or just pauses until
    # it needs more to meet the limit.
    token_proxy_limit = cli.SwitchAttr(
        "--token_proxy_limit", int,
        default=10,
        group=__group__,
        help="The maximum number of proxies."
    )

    token_proxy_countries = ConfigConstant(None)
    token_proxy_types = ConfigConstant([('HTTP', ('Anonymous', 'High')), 'HTTPS'])

    # All Below... Only Applicable for .serve() Method (I think...)
    token_http_allowed_codes = ConfigConstant([200, 301, 302, 400])
    token_prefer_connect = ConfigConstant(True)
    token_post = ConfigConstant(False)

    token_min_req_proxy = cli.SwitchAttr(
        "--token_min_req_proxy", int,
        default=5,
        group=__group__,
        help=(
            "The minimum number of processed requests to estimate the quality "
            "of proxy (in accordance with max_error_rate and max_resp_time)"
        )
    )


class TokenProxyPoolArgs(ConfigArgs):

    __group__ = 'Token Proxy Pool'
    __prefix__ = 'token'

    # Since we are not using the .serve() method, we use these manually instead
    # of providing to the .find() method.
    token_proxy_max_error_rate = cli.SwitchAttr(
        "--token_proxy_max_error_rate", float,
        default=0.5,
        group=__group__,
    )
    token_proxy_max_resp_time = cli.SwitchAttr(
        "--token_proxy_max_resp_time", int,
        default=8,
        group=__group__,
    )
    token_proxy_max_wait_time = cli.SwitchAttr(
        "--token_proxy_max_wait_time", int,
        default=8,
        group=__group__,
    )
    token_proxy_pool_max_wait_time = cli.SwitchAttr(
        "--token_proxy_pool_max_wait_time", int,
        default=25,
        group=__group__,
    )


class TokenRequestArgs(ConfigArgs):

    __group__ = 'Token Requests'
    __prefix__ = 'token'
    __second_prefix__ = 'connector'

    # We should probably be using the force close option.
    token_connection_force_close = cli.Flag(
        "--token_connection_force_close",
        group=__group__,
        help="Close underlying sockets after connection releasing (optional)."
    )
    token_connection_keepalive_timeout = cli.SwitchAttr(
        "--token_connection_keepalive_timeout", float,
        default=3.0,
        group=__group__,
        help=(
            "Timeout for connection/session reusing after releasing. \n"
            "For disabling keep-alive feature use force_close=True flag."
        )
    )
    # Connection Limits for Connectors
    token_connection_limit = cli.SwitchAttr(
        "--token_connection_limit", int,
        default=200,
        group=__group__,
        help="Total number simultaneous connections for the connector."
    )
    token_connection_limit_per_host = cli.SwitchAttr(
        "--token_connection_limit_per_host", int,
        default=0,  # No Limit - Default
        group=__group__,
        help="Limit simultaneous connections to the same endpoint."
    )
    token_connection_timeout = cli.SwitchAttr(
        "--token_connection_timeout", int,
        default=5,
        group=__group__,
        help="Session timeout for requests."
    )


class PasswordProxyBrokerArgs(ConfigArgs):

    __group__ = "Password Broker"
    __prefix__ = 'pw'

    pw_max_conn = cli.SwitchAttr(
        "--pw_max_conn", int,
        default=200,
        group=__group__,
        help="The maximum number of concurrent checks of proxies."
    )
    pw_max_tries = cli.SwitchAttr(
        "--pw_max_tries", int,
        default=2,
        group=__group__,
        help="The maximum number of attempts to check a proxy."
    )

    pw_verify_ssl = ConfigConstant(False)


class PasswordProxyServerArgs(ConfigArgs):

    __group__ = 'Password Proxy Server'
    __prefix__ = 'pw'
    __second_prefix__ = 'proxy'

    # Not sure if it stops completely after this limit?  Or just pauses until
    # it needs more to meet the limit.
    pw_proxy_limit = cli.SwitchAttr(
        "--pw_proxy_limit", int,
        default=200,
        group=__group__,
        help="The maximum number of proxies."
    )

    pw_proxy_countries = ConfigConstant(None)
    pw_proxy_types = ConfigConstant(['HTTP', 'HTTPS'])

    # All Below... Only Applicable for .serve() Method (I think...)
    pw_http_allowed_codes = ConfigConstant([200, 201, 301, 302, 400])
    pw_prefer_connect = ConfigConstant(True)
    pw_post = ConfigConstant(True)

    pw_min_req_proxy = cli.SwitchAttr(
        "--pw_min_req_proxy", int,
        default=5,
        group=__group__,
        help=(
            "The minimum number of processed requests to estimate the quality "
            "of proxy (in accordance with max_error_rate and max_resp_time)"
        )
    )


class PasswordProxyPoolArgs(ConfigArgs):
    """
    We need to make this work better with our pool, the min_req_per_proxy thing
    does not make sense when they are done sequentially - you hit too many request
    errors.
    """

    __group__ = 'Password Proxy Pool'
    __prefix__ = 'pw'

    # Since we are not using the .serve() method, we use these manually instead
    # of providing to the .find() method.
    pw_proxy_max_error_rate = cli.SwitchAttr(
        "--pw_proxy_max_error_rate", float,
        default=0.3,
        group=__group__,
    )
    pw_proxy_max_resp_time = cli.SwitchAttr(
        "--pw_proxy_max_resp_time", int,
        default=8,
        group=__group__,
    )
    pw_proxy_max_wait_time = cli.SwitchAttr(
        "--pw_proxy_max_wait_time", int,
        default=8,
        group=__group__,
    )
    pw_proxy_pool_max_wait_time = cli.SwitchAttr(
        "--pw_proxy_pool_max_wait_time", int,
        default=25,
        group=__group__,
    )


class PasswordRequestArgs(ConfigArgs):

    __group__ = 'Password Requests'
    __prefix__ = 'pw'
    __second_prefix__ = 'connector'

    # We should probably be using the force close option.
    pw_connection_force_close = cli.Flag(
        "--pw_connection_force_close",
        group=__group__,
        help="Close underlying sockets after connection releasing (optional)."
    )
    pw_connection_keepalive_timeout = cli.SwitchAttr(
        "--pw_connection_keepalive_timeout", float,
        default=3.0,
        group=__group__,
        help=(
            "Timeout for connection/session reusing after releasing. \n"
            "For disabling keep-alive feature use force_close=True flag."
        )
    )
    # Connection Limits for Connectors
    pw_connection_limit = cli.SwitchAttr(
        "--pw_connection_limit", int,
        default=200,
        group=__group__,
        help="Total number simultaneous connections for the connector."
    )
    pw_connection_limit_per_host = cli.SwitchAttr(
        "--pw_connection_limit_per_host", int,
        default=0,  # No Limit - Default
        group=__group__,
        help="Limit simultaneous connections to the same endpoint."
    )
    pw_connection_timeout = cli.SwitchAttr(
        "--pw_connection_timeout", int,
        default=6,
        group=__group__,
        help="Session timeout for requests."
    )


class PasswordProxyArgs(PasswordProxyPoolArgs, PasswordProxyServerArgs, PasswordProxyBrokerArgs):

    @property
    def pw_proxy_server_conf(self):
        return self.config_for_class(PasswordProxyServerArgs)

    @property
    def pw_proxy_pool_conf(self):
        return self.config_for_class(PasswordProxyPoolArgs)

    @property
    def pw_proxy_conf(self):
        return self.config_for_class(PasswordProxyPoolArgs, PasswordProxyServerArgs,
            PasswordProxyBrokerArgs)


class TokenProxyArgs(TokenProxyPoolArgs, TokenProxyServerArgs, TokenProxyBrokerArgs):

    @property
    def token_proxy_server_conf(self):
        return self.config_for_class(TokenProxyServerArgs)

    @property
    def token_proxy_pool_conf(self):
        return self.config_for_class(TokenProxyPoolArgs)

    @property
    def token_proxy_conf(self):
        return self.config_for_class(TokenProxyPoolArgs, TokenProxyServerArgs, TokenProxyBrokerArgs)


class TokenArgs(TokenRequestArgs, TokenProxyArgs):

    @property
    def token_request_conf(self):
        return self.config_for_class(TokenRequestArgs)

    @property
    def token_conf(self):
        config = self.token_proxy_conf
        config.update(**self.token_request_conf)
        return config


class PasswordArgs(PasswordProxyArgs, PasswordRequestArgs):

    password_limit = cli.SwitchAttr("--pwlimit", int, default=None)

    @property
    def pw_request_conf(self):
        return self.config_for_class(PasswordRequestArgs)

    @property
    def pw_conf(self):
        config = self.pw_proxy_conf
        config.update(**self.pw_request_conf)
        config['password_limit'] = self.password_limit
        return config


class ProxyArgs(PasswordProxyArgs, TokenProxyArgs):
    pass


class AttackArgs(PasswordArgs, TokenArgs):
    pass
