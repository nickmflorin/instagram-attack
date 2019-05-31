def positive_int(required=True, **kwargs):
    config = {
        'required': required,
        'type': 'integer',
        'min': 0,
    }
    config.update(**kwargs)
    return config


def positive_float(required=True, **kwargs):
    config = {
        'required': required,
        'type': 'float',
        'min': 0.0,
    }
    config.update(**kwargs)
    return config


def boolean(required=True, **kwargs):
    config = {
        'required': required,
        'type': 'boolean'
    }
    config.update(**kwargs)
    return config


def log_level(**kwargs):
    to_level = lambda v: v.upper()  # noqa
    config = {
        'required': True,
        'type': 'string',
        # 'coerce': (str, to_level),
    }
    config.update(**kwargs)
    return config


def limit(required=False):
    config = {
        'required': required,
        'type': 'dict',
        'schema': {
            'historical': positive_int(required=False, nullable=True),
            'active': positive_int(required=False, nullable=True),
        }
    }
    return config


LimitsSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'errors': {
            'required': False,
            'type': 'dict',
            'schema': {
                'all': limit(),
                'connection': limit(),
                'ssl': limit(),
                'timeout': limit(),
                'instagram': limit(),
                'response': limit(),
            }
        },
        'requests': {
            'required': False,
            'type': 'dict',
            'schema': {
                'all': limit(),
                'success': limit(),
                'fail': limit(),
            }
        },
        'error_rate': {
            'required': False,
            'type': 'dict',
            'schema': {
                'historical': positive_int(required=False, nullable=True),
                'active': positive_int(required=False, nullable=True),
                'horizon': positive_int(max=10, default=5, required=False)
            }
        },
        # TODO: Allow Historical & Current
        'resp_time': positive_float(max=10.0, nullable=True, required=False),
        'time_since_used': positive_float(max=20.0, nullable=True, required=False),
        'too_many_requests_delay': positive_int(default=10),
    }
}


PoolSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'collect': boolean(),
        'timeout': positive_int(max=25),
        'save_method': {'oneof_regex': ['conclusively', 'iteratively']},
    }
}

BrokerSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'max_conn': positive_int(max=1000),
        'max_tries': positive_int(max=10),
        'timeout': positive_int(max=10),
    },
}


ProxySchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'pool': PoolSchema,
        'broker': BrokerSchema,
        'limits': LimitsSchema
    }
}

AttackSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'batch_size': positive_int(max=100),
        'attempts': {
            'required': True,
            'type': 'dict',
            'schema': {
                'batch_size': positive_int(max=100),
            }
        }
    }
}

ConnectionSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'limit_per_host': positive_int(max=100, default=10),
        'timeout': positive_int(max=20, default=10),
        'limit': positive_int(max=200, default=100),  # Might want to raise max higher.
    }
}

LoggingSchema = {
    'required': True,
    'type': dict,
    'schema': {
        'level': {
            'type': 'string',
            'required': False,
            'default': 'info',
            'oneof_regex': ['debug', 'info', 'warning', 'error', 'critical']
        },
        'request_errors': boolean(default=False, required=False)
    }
}

Schema = {
    'instattack': {
        'required': True,
        'type': 'dict',
        'schema': {
            'attack': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'batch_size': positive_int(max=100),
                    'attempts': {
                        'required': True,
                        'type': 'dict',
                        'schema': {
                            'batch_size': positive_int(max=100),
                        }
                    }
                }
            },
            'proxies': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'pool': PoolSchema,
                    'broker': BrokerSchema,
                    'limits': LimitsSchema
                }
            },
            'connection': {
                'required': True,
                'type': 'dict',
                'schema': {
                    'limit_per_host': positive_int(max=100, default=10),
                    'timeout': positive_int(max=20, default=10),
                    'limit': positive_int(max=200, default=100),  # Might want to raise max higher.
                }
            },
            # 'log.logging': {
            #     'required': True,
            #     'type': dict,
            #     'schema': {
            #         'level': {
            #             'type': 'string',
            #             'required': False,
            #             'default': 'info',
            #             'oneof_regex': ['debug', 'info', 'warning', 'error', 'critical']
            #         },
            #         'request_errors': boolean(default=False, required=False)
            #     }
            # }
        }
    }
}
