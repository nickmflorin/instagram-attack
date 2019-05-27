from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

from instattack import settings
from instattack.src.utils import humanize_list


@dataclass
class AttributeEvaluation:

    attr: str
    relative_value: Any
    value: Any

    comparison: str = ">"
    name: str = field(init=False, repr=True)
    strict: bool = False

    def __post_init__(self):
        self.name = settings.PROXY_FORMAL_ATTRS[self.attr]

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
