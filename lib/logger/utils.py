
def flexible_retrieval(record, param, tier_key=None):
    """
    Priorities overridden values explicitly provided in extra, and will
    check record.extra['context'] if the value is not in 'extra'.

    If tier_key is provided and item found is object based, it will try
    to use the tier_key to get a non-object based value.
    """
    def flexible_obj_get(value):
        if hasattr(value, '__dict__') and tier_key:
            return getattr(value, tier_key)
        return value

    if record.extra.get(param):
        return flexible_obj_get(record.extra[param])
    else:
        if hasattr(record, param):
            return getattr(record, param)
        else:
            if record.extra.get('context'):
                ctx = record.extra['context']
                if hasattr(ctx, param):
                    value = getattr(ctx, param)
                    return flexible_obj_get(value)
        return None


def optional_indent(no_indent=False):
    def _opt_indent(val):
        if not no_indent:
            return val
        return 0
    return _opt_indent
