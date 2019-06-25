"""
[!] Temporarily Deprecated
----------------------
We are not currently using Cerberus schema validation.
"""


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
        'always_include_confirmed': boolean(default=True),
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

TimeoutSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        # TODO: Add validation rule that the default start amount must be greater
        # than or equal to the increment.
        'too_many_requests': {
            'required': True,
            'type': 'dict',
            'schema': {
                'increment': positive_int(max=60, default=10),
                'start': positive_int(max=60, default=10),
            }
        },
        'too_many_open_connections': {
            'required': True,
            'type': 'dict',
            'schema': {
                'increment': positive_int(max=60, default=10),
                'start': positive_int(max=60, default=10),
            }
        },
    }
}


PoolSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'collect': boolean(),
        'timeout': positive_int(max=25),
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
        'limits': LimitsSchema,
        'timeouts': TimeoutSchema,
        'save_method': {
            'required': True,
            'type': 'string',
            # 'oneof_regex': ['end', 'live']
        },
        'train': {
            'required': True,
            'type': dict,
            'schema': {
                'batch_size': positive_int(max=100),
            }
        }
    }
}

PasswordsSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'batch_size': positive_int(max=100),
        'generator': {
            'required': True,
            'type': 'dict',
            'schema': {
                'numerics': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'before': boolean(default=False),
                        'after': boolean(default=True),
                        'birthday': {
                            'required': True,
                            'type': 'dict',
                            'schema': {
                                'provided': boolean(default=True),
                                'all': boolean(default=False),
                                # TODO: Make these required if `all` is set to True.
                                # Also, want to validate as a valid year.
                                'start_year': positive_int(nullable=True, required=False),
                                'end_year': positive_int(nullable=True, required=False)
                            }
                        }
                    }
                },
                'alterations': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'before': boolean(default=False),
                        'after': boolean(default=True),
                    }
                },
                # [x] TODO: This will still allow lists with strings or other
                # non-integers in them.
                'capitalize_at_indices': {
                    'type': ['integer', 'list'],
                    'schema': {'type': ['integer', 'list']}
                }
            }
        }
    }
}

AttemptsSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'batch_size': positive_int(max=100),
        'save_method': {
            'type': 'string',
            'oneof_regex': ['end', 'live']
        },
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

# LoggingSchema = {
#     'required': True,
#     'type': dict,
#     'schema': {
#         'level': {
#             'required': True,
#             'type': 'string',
#             'anyof': [
#                 {'regex': 'debug'},
#                 {'regex': 'info'},
#                 {'regex': 'warning'},
#                 {'regex': 'error'},
#                 {'regex': 'critical'},
#             ]
#         },
#         'request_errors': boolean(default=False, required=False)
#     }
# }

Schema = {
    'passwords': PasswordsSchema,
    'attempts': AttemptsSchema,
    'proxies': ProxySchema,
    'pool': PoolSchema,
    'broker': BrokerSchema,
    'connection': ConnectionSchema
    # 'log.logging': LoggingSchema,
}
