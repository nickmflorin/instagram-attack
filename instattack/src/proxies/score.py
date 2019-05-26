from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

from instattack.src.utils import humanize_list


PROXY_PRIORITY_FIELDS = (
    (-1, 'num_successful_requests'),
    (1, 'num_connection_errors'),
    (1, 'avg_resp_time'),
)

FORMAL_ATTRS = {
    'num_active_requests': 'Num. Active Requests',
    'flattened_error_rate': 'Flat. Error Rate',
    'avg_resp_time': 'Avg. Response Time',
    'time_since_used': 'Time Since Used',
    'num_connection_errors': 'Num. Connection Errors'
}


@dataclass
class AttributeEvaluation:

    attr: str
    relative_value: Any
    value: Any

    comparison: str = ">"
    name: str = field(init=False, repr=True)
    strict: bool = False

    def __post_init__(self):
        self.name = FORMAL_ATTRS[self.attr]

    def __str__(self):
        return f"{self.name} {self.value} {self.comparison} {self.relative_value}"


@dataclass
class ProxyEvaluation:

    reasons: List[AttributeEvaluation]

    def add(self, evaluation):
        self.reasons.append(evaluation)

    @property
    def passed(self):
        return len(self.reasons) == 0

    def __str__(self):
        if self.passed:
            return 'Evaluation Passed'
        else:
            return humanize_list([str(reason) for reason in self.reasons])


def priority_values(proxy):
    return [
        field[0] * getattr(proxy, field[1])
        for field in PROXY_PRIORITY_FIELDS
    ]


def priority(proxy, count):
    priority = priority_values(proxy)
    priority.append(count)
    return tuple(priority)


def evaluate(
    proxy,
    num_active_requests=None,
    flattened_error_rate=None,
    avg_resp_time=None,
    num_connection_errors=None,
    time_since_used=None,
):
    """
    Determines if the proxy meets the provided standards.

    [x] TODO:
    --------
    Audit the use of `strict` as a parameter and how we are generating these
    evaluations, whether or not all the information they contain is necessary.

    Right now, we haven't really figured out a better meaning for `strict`
    other than the fact that it means the proxy will be removed/not put
    in queue.  This is kind of pointless because we could also just not
    include the `value`, but we might have better reasons for `strict` soon.

    [!] IMPORTANT:
    -------------
    We should rely less on the value of response time and min_req_proxy, if
    the proxy has very good metrics (i.e. is very successful but was used
    a lot or has a higher response time).
    """
    evaluations = ProxyEvaluation(reasons=[])

    if num_active_requests and proxy.num_active_requests > num_active_requests:
        evaluations.add(AttributeEvaluation(
            value=proxy.num_active_requests,
            relative_value=num_active_requests,
            attr="num_active_requests"
        ))

    if flattened_error_rate and proxy.flattened_error_rate > flattened_error_rate:
        evaluations.add(AttributeEvaluation(
            value=proxy.flattened_error_rate,
            relative_value=flattened_error_rate,
            attr="flattened_error_rate"
        ))

    if avg_resp_time and proxy.avg_resp_time > avg_resp_time:
        evaluations.add(AttributeEvaluation(
            value=proxy.avg_resp_time,
            relative_value=avg_resp_time,
            attr="avg_resp_time"
        ))

    if num_connection_errors and proxy.num_connection_errors > num_connection_errors:
        evaluations.add(AttributeEvaluation(
            value=proxy.num_connection_errors,
            relative_value=num_connection_errors,
            attr="num_connection_errors"
        ))

    if time_since_used and proxy.time_since_used != 0.0 and proxy.time_since_used < time_since_used:
        evaluations.add(AttributeEvaluation(
            value=proxy.time_since_used,
            relative_value=time_since_used,
            attr="time_since_used",
            comparison="<"
        ))

    return evaluations


def evaluate_for_pool(proxy, config):
    """
    Called before a proxy is put into the Pool.

    Allows us to disregard or completely ignore proxies without having
    to delete them from DB.

    [x] TODO:
    --------
    Incorporate limit on certain errors or exclusion of proxy based on certain
    errors in general.

    Make it so that we can return the evaluations and also indicate
    that it is okay or not okay for the pool.
    """
    flattened_error_rate = config.get('max_error_rate')
    avg_resp_time = config.get('max_resp_time')
    num_active_requests = config.get('max_req_proxy')
    num_connection_errors = config.get('max_connection_errors')
    num_connection_errors = config.get('max_connection_errors')

    evaluation = evaluate(
        proxy,
        flattened_error_rate=flattened_error_rate,
        avg_resp_time=avg_resp_time,
        num_active_requests=num_active_requests,
        num_connection_errors=num_connection_errors,
    )

    return evaluation


def evaluate_for_use(proxy, config):
    """
    Called before a proxy is returned from the Pool.  This is where we want to
    evaluate things that would not prevent a proxy from going into the pool,
    but just from being pulled out at that moment.

    This should incorporate timing aspects and things of that nature.
    Can include more custom logic indicating the desired use of the
    proxy than we can do with the priority alone.
    """

    # TODO: We should only restrict time since last used if the last request was
    # a too many request error.
    time_since_used = config.get('min_time_between_proxy')
    evaluation = evaluate(
        proxy,
        time_since_used=time_since_used,
    )
    return evaluation
