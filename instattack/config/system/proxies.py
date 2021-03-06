from instattack.config import fields

LIMITS = fields.SetField(
    name='LIMITS',
    # TODO: Allow Historical & Current
    RESP_TIME=fields.PositiveFloatField(
        default=None,
        optional=True,
        help=(
            "The maximum response time in seconds. If proxy.avg_resp_time exceeds this "
            "value, proxy will be removed from the pool."
        ),
    ),

    REQUESTS=fields.SetField(
        ALL=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=None),
            ACTIVE=fields.PositiveIntField(optional=True, default=None),
        ),
        SUCCESS=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=None),
            ACTIVE=fields.PositiveIntField(optional=True, default=None),
        ),
        FAIL=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=None),
            ACTIVE=fields.PositiveIntField(optional=True, default=None),
        ),
        help=(
            "The maxmium number of allowed requests for each proxy per attack, before "
            "being removed from pool.  For LARGER attacks, this should probably be "
            "negated, since we do not want to discard good proxies."
        )
    ),

    # TODO: Start Measuring Historical & Active
    ERROR_RATE=fields.SetField(
        HISTORICAL=fields.PositiveFloatField(optional=True, default=None),
        ACTIVE=fields.PositiveFloatField(optional=True, default=None),
        HORIZON=fields.PositiveIntField(
            default=5,
            max=30,
            help="The minimum number of requests required before error rate is non-zero."
        ),
        help=(
            "The maximum number of allowed errors for a proxy before being "
            "removed from the pool or not included in pool to begin with."
        )
    ),

    ERRORS=fields.SetField(
        ALL=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=2),
            ACTIVE=fields.PositiveIntField(optional=True, default=1),
        ),
        CONNECTION=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=2),
            ACTIVE=fields.PositiveIntField(optional=True, default=1),
        ),
        RESPONSE=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=2),
            ACTIVE=fields.PositiveIntField(optional=True, default=1),
        ),
        INSTAGRAM=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=1),
            ACTIVE=fields.PositiveIntField(optional=True, default=1),
        ),
        SSL=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=3),
            ACTIVE=fields.PositiveIntField(optional=True, default=2),
        ),
        # [x] NOTE:
        # --------
        # There seem to be a lot of proxies that do get confirmed results
        # but also have a lot of historical timeout errors.
        TIMEOUT=fields.SetField(
            HISTORICAL=fields.PositiveIntField(optional=True, default=4),
            ACTIVE=fields.PositiveIntField(optional=True, default=2),
        ),
        help=(
            "The maximum number of allowed errors for a proxy before being "
            "removed from the pool or not included in pool to begin with."
        )
    ),
)

POOL = fields.SetField(
    name='POOL',
    TIMEOUT=fields.PositiveIntField(
        default=10,
        max=30,
        help="The maximum amount of time to wait for a proxy from the queue before failing."
    ),
    COLLECT=fields.BooleanField(default=False),

    # [x] NOTE:
    # --------
    # 3 Purposes:
    #   (1) Initial Population of Confirmed Queue
    #   (2) Whether or Not Evaluation Can be Ignored
    #   (3) Whether or not Error Causes Confirmed Proxy to be Removed
    # Right now this checks if both are satisfied, but we might want the ability
    # to check if either is specified, and over what range.
    CONFIRMATION=fields.SetField(
        THRESHOLD=fields.PositiveIntField(
            default=2,
            max=10,
        ),
        HORIZON=fields.PositiveIntField(
            default=5,
            max=20,
        ),
        THRESHOLD_IN_HORIZON=fields.PositiveIntField(
            default=1,
            optional=True,
            max=20,  # TODO: Might want to set max based on THRESHOLD and HORIZON
        ),
    ),
    # [x] NOTE:
    # --------
    # We do not need the confirmed fields since they already are factored
    # in based on the separate queues.
    PRIORITY=fields.SeriesField([
        (-1, ('requests', 'active', 'success')),
        (1, ('error_rate', 'active')),
        (-1, ('requests', 'historical', 'success')),
        (1, ('error_rate', 'historical')),
        (1, ('avg_resp_time')),
    ]),

    TIMEOUTS=fields.SetField(
        # TODO: Add Max Values to these Parameters
        TOO_MANY_REQUESTS=fields.SetField(
            INCREMENT=fields.PositiveIntField(
                default=5,
            ),
            START=fields.PositiveIntField(
                default=5,
            ),
            MAX=fields.PositiveIntField(
                default=40,
            ),
        ),
        TOO_MANY_OPEN_CONNECTIONS=fields.SetField(
            INCREMENT=fields.PositiveIntField(
                default=5,
            ),
            START=fields.PositiveIntField(
                default=5,
            ),
            MAX=fields.PositiveIntField(
                default=40,
            ),
        ),
        help=(
            "The amount of time to wait before using a proxy that raises an error "
            "that does not indicate an invalid proxy.  After the max value has been reached "
            "via incrementation, the proxy will be discarded."
        )
    ),
    LIMITS=LIMITS,
)

"""
[x] NOTE:
--------
Settings Here Only Matter if Collect = True
Do we want to add a limit to the broker collection?
"""
BROKER = fields.SetField(
    name='BROKER',
    MAX_CONN=fields.PositiveIntField(
        default=200,
        max=500,
        help="The maximum number of concurrent checks of proxies."
    ),
    # [x] NOTE:
    # --------
    # Note that the lower the value of max_tries, the faster the broker will return
    # proxies, but they will not contain as much information to gauge their
    # relative reliability and speed.
    MAX_TRIES=fields.PositiveIntField(
        default=2,
        max=5,
        help="The maximum number of attempts to check a proxy."
    ),
    TIMEOUT=fields.PositiveIntField(
        default=5,
        max=10,
        help="Maximum amount of time to wait for broker to return a proxy before failing."
    )
)


PROXIES = fields.SetField(
    name='PROXIES',

    # Non-Configurable Fields
    # --------------------------------------------------------------------------
    ERRORS=fields.SetField(

        PROXY_BROKER_TRANSLATION=fields.SetField(
            connection_error='client_connection',
            configurable=False,
            help=(
                "Responsible for translating HTTP errors for proxies retrieved "
                "from the proxy broker package into our error classification "
                "scheme."
            )
        ),
        # [x] TODO: Make These More Granular
        CLASSIFICATION=fields.SetField(
            connection=(
                'client_connection',
                'proxy_connection',
                'server_connection',
            ),
            timeout=(
                'timeout',
            ),
            ssl=(
                'ssl',
            ),
            client={
                'proxy_auth',
                'proxy_client',
            },
            instagram=(
                'invalid_instagram_result',
            ),
            invalid_response=(
                'invalid_response_json',
                'invalid_response',
            ),
            configurable=False,
        ),
        # [x] TODO: Maybe we should move these to CLASSIFICATION?  Even though we do
        # not store these errors in the DB?
        TIMEOUT=[
            'too_many_requests',
            'too_many_open_connections'
        ],
    ),
    # TODO: Maybe turn into a configurable choice field.
    SAVE_METHOD=fields.ConstantField('end'),
    TYPES=["HTTP"],

    # Configurable Fields
    # --------------------------------------------------------------------------

    COUNTRIES=fields.SeriesField(
        default=['US'],
        values={
            'type': str,
        },
    ),

    TRAIN=fields.SetField(
        BATCH_SIZE=fields.PositiveIntField(
            default=50,
            max=100,
        ),
    ),

    BROKER=BROKER,
    POOL=POOL,
)
