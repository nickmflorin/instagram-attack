def positive_int(**kwargs):
    config = {
        'required': True,
        'type': 'integer',
        'min': 0,
    }
    config.update(**kwargs)
    return config


def positive_float(**kwargs):
    config = {
        'required': True,
        'type': 'float',
        'min': 0.0,
    }
    config.update(**kwargs)
    return config


def boolean(**kwargs):
    config = {
        'required': True,
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


def limit(**kwargs):
    config = {
        'required': False,
        'type': 'dict',
        'schema': {
            'historical': positive_int(nullable=True),
            'active': positive_int(nullable=True),
        }
    }
    config['schema'].update(**kwargs)
    return config


LimitsSchema = {
    'required': False,
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
                'historical': positive_int(nullable=True),
                'active': positive_int(nullable=True),
                'horizon': positive_int(max=10, default=5, nullable=True)
            }
        },
        'resp_time': positive_float(max=10.0, nullable=True),  # TODO: Allow Historical & Current
        'time_since_used': positive_float(max=20.0, nullable=True),
        'too_many_requests_delay': positive_int(default=10),
    }
}


PoolSchema = {
    'required': True,
    'type': 'dict',
    'schema': {
        'limits': LimitsSchema,
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
        'collect': boolean(),
        'pool': PoolSchema,
        'broker': BrokerSchema
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
        },
        'connection': {
            'required': True,
            'type': 'dict',
            'schema': {
                'limit_per_host': positive_int(max=100, default=10),
                'timeout': positive_int(max=20, default=10),
                'limit': positive_int(max=200, default=100),  # Might want to raise max higher.
            }
        }
    }
}

Schema = {
    'instattack': {
        'required': True,
        'type': 'dict',
        'schema': {
            'attack': AttackSchema,
            'proxies': ProxySchema
        }
    }
}
