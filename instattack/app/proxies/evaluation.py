from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

from instattack.lib.utils import humanize_list


PROXY_FORMAL_ATTRS = {
    'num_active_requests': 'Num. Active Requests',
    'flattened_error_rate': 'Flat. Error Rate',
    'avg_resp_time': 'Avg. Response Time',
    'time_since_used': 'Time Since Used',
    'num_connection_errors': 'Num. Connection Errors',
    'num_response_errors': 'Num. Invalid Response Errors',
    'num_ssl_errors': 'Num. SSL Connection Errors',
    'num_instagram_errors': 'Num. Instagram Identified Errors',
    'num_timeout_errors': 'Num. Timeout Errors',
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
        self.name = PROXY_FORMAL_ATTRS[self.attr]

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


def evaluate(proxy, config):
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
    config = config['proxies']['pool']
    evaluations = ProxyEvaluation(reasons=[])

    max_params = (
        ('max_requests', 'num_active_requests'),
        ('max_resp_time', 'avg_resp_time'),
        ('max_error_rate', 'flattened_error_rate'),
        ('max_response_errors', 'num_response_errors'),
        ('max_instagram_errors', 'num_instagram_errors'),
        ('max_timeout_errors', 'num_timeout_errors'),
        ('max_connection_errors', 'num_connection_errors'),
        ('max_ssl_errors', 'num_ssl_errors'),
    )

    for param_set in max_params:
        value = getattr(proxy, param_set[1])
        relative_value = config.get(param_set[0])
        if relative_value:
            if value > relative_value:
                evaluations.add(AttributeEvaluation(
                    value=value,
                    relative_value=relative_value,
                    attr=param_set[1]
                ))

    return evaluations
