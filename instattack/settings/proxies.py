from instattack.config import fields


PROXIES = fields.SetField(

    # Non-Configurable Fields
    # --------------------------------------------------------------------------

    PROXY_BROKER_ERROR_TRANSLATION=fields.ConstantSetField(
        connection_error='client_connection',
    ),

    # Used to Generalize Errors in Priority
    # [x] TODO: Make These More Granular
    ERROR_TYPE_CLASSIFICATION=fields.ConstantSetField(
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
    ),

    TIMEOUT_ERRORS=fields.ConstantField([
        'too_many_requests',
        'too_many_open_connections'
    ]),

    PROXY_TYPES=fields.ConstantField(["HTTP"]),

    SAVE_METHOD=fields.ConstantField('end'),

    # Configurable Fields
    # --------------------------------------------------------------------------

    COUNTRIES=fields.ListField(
        default=['US'],
        type=str,
    ),

    TRAIN=fields.SetField(
        BATCH_SIZE=fields.PositiveIntField(
            default=50,
            max=100,
        ),
    ),

    # [x] NOTE:
    # --------
    # Settings Here Only Matter if Collect = True
    # Do we want to add a limit to the broker collection?
    BROKER=fields.SetField(
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
    ),
    POOL=fields.SetField(
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
        PRIORITY=fields.PriorityField(
            [-1, ['requests', 'active', 'success']],
            [1, ['error_rate', 'active']],
            [-1, ['requests', 'historical', 'success']],
            [1, ['error_rate', 'historical']],
            [1, ['avg_resp_time']]
        ),

        TIMEOUTS=fields.SetField(
            TOO_MANY_REQUESTS=fields.SetField(
                INCREMENT=fields.PositiveIntField(
                    default=5,
                    # TODO: Add Max
                ),
                START=fields.PositiveIntField(
                    default=5,
                    # TODO: Add Max
                ),
                MAX=fields.PositiveIntField(
                    default=40,
                    # TODO: Add Max
                ),
            ),
            TOO_MANY_OPEN_CONNECTIONS=fields.SetField(
                INCREMENT=fields.PositiveIntField(
                    default=5,
                    # TODO: Add Max
                ),
                START=fields.PositiveIntField(
                    default=5,
                    # TODO: Add Max
                ),
                MAX=fields.PositiveIntField(
                    default=40,
                    # TODO: Add Max
                ),
            ),
            help=(
                "The amount of time to wait before using a proxy that raises an error "
                "that does not indicate an invalid proxy.  After the max value has been reached "
                "via incrementation, the proxy will be discarded."
            )
        ),

        LIMITS=fields.SetField(
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
    ),
)
