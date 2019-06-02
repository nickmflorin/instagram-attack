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
