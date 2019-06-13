from dataclasses import dataclass
from typing import List, Any

from termx import humanize_list

from instattack.config import config


@dataclass
class AttributeEvaluation:

    name: str
    relative_value: Any
    value: Any
    comparison: str = ">"

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

    def merge(self, *evaluations):
        for evaluation in evaluations:
            for reason in evaluation.reasons:
                self.add(reason)


def evaluate_errors(proxy):

    errors = config['proxies']['pool']['limits'].get('errors', {})
    evaluations = ProxyEvaluation(reasons=[])

    max_params = [
        ('all', (), ),
        ('connection', ('connection', )),
        ('response', ('response', )),
        ('ssl', ('ssl', )),
        ('timeout', ('timeout', )),
        ('instagram', ('instagram', )),
    ]

    for param_set in max_params:
        config_errors = errors.get(param_set[0])
        if config_errors:
            config_active_errors = config_errors.get('active')
            if config_active_errors:
                actual_active_errors = proxy.num_errors(*param_set[1], active=True)

                if actual_active_errors > config_active_errors:
                    reason = AttributeEvaluation(
                        value=actual_active_errors,
                        relative_value=config_active_errors,
                        name=f"{param_set[0]} Active Errors".title(),
                    )
                    evaluations.add(reason)

            config_hist_errors = config_errors.get('historical')
            if config_hist_errors:
                actual_hist_errors = proxy.num_errors(*param_set[1], active=False)

                if actual_hist_errors > config_hist_errors:
                    reason = AttributeEvaluation(
                        value=actual_hist_errors,
                        relative_value=config_hist_errors,
                        name=f"{param_set[0]} Historical Errors".title(),
                    )
                    evaluations.add(reason)
    return evaluations


def evaluate_requests(proxy):

    evaluations = ProxyEvaluation(reasons=[])
    requests = config['proxies']['pool']['limits'].get('requests', {})

    max_params = [
        ('all', (None, ), ),
        ('success', (True, )),
        ('fail', (False, )),
    ]

    for param_set in max_params:
        config_requests = requests.get(param_set[0])
        if config_requests:

            config_active_requests = config_requests.get('active')
            if config_active_requests:
                actual_active_requests = proxy.num_requests(active=True, success=param_set[1])

                if param_set[0] == 'success':
                    if actual_active_requests < config_active_requests:
                        reason = AttributeEvaluation(
                            value=actual_active_requests,
                            relative_value=config_active_requests,
                            name=f"{param_set[0]} Active Requests".title(),
                            comparison="<"
                        )
                        evaluations.add(reason)
                else:
                    if actual_active_requests > config_active_requests:
                        reason = AttributeEvaluation(
                            value=actual_active_requests,
                            relative_value=config_active_requests,
                            name=f"{param_set[0]} Active Requests".title(),
                        )
                        evaluations.add(reason)

            config_hist_requests = config_requests.get('historical')
            if config_hist_requests:
                actual_hist_requests = proxy.num_requests(active=False, success=param_set[1])

                if param_set[0] == 'success':
                    if actual_hist_requests < config_hist_requests:
                        reason = AttributeEvaluation(
                            value=actual_hist_requests,
                            relative_value=config_hist_requests,
                            name=f"{param_set[0]} Historical Requests".title(),
                            comparison="<"
                        )
                        evaluations.add(reason)
                    else:
                        if actual_hist_requests < config_hist_requests:
                            reason = AttributeEvaluation(
                                value=actual_hist_requests,
                                relative_value=config_hist_requests,
                                name=f"{param_set[0]} Historical Requests".title(),
                            )
                            evaluations.add(reason)

    return evaluations


def evaluate_error_rate(proxy):

    evaluations = ProxyEvaluation(reasons=[])
    limits = config['proxies']['pool']['limits']

    if limits.get('error_rate'):
        config_error_rate = limits['error_rate']

        config_active_rate = config_error_rate.get('active')
        if config_active_rate:
            actual_active_rate = proxy.error_rate(active=True)

            if actual_active_rate > config_active_rate:
                reason = AttributeEvaluation(
                    value=actual_active_rate,
                    relative_value=config_active_rate,
                    name=f"Active Error Rate".title(),
                )
                evaluations.add(reason)

        config_hist_rate = config_error_rate.get('historical')
        if config_hist_rate:
            actual_hist_rate = proxy.error_rate(active=False)

            if actual_hist_rate > config_hist_rate:
                reason = AttributeEvaluation(
                    value=actual_hist_rate,
                    relative_value=config_hist_rate,
                    name=f"Historical Error Rate".title(),
                )
                evaluations.add(reason)
    return evaluations


def evaluate(proxy):
    """
    Determines if the proxy meets the provided standards to be put into the pool,
    versus `evaluate_from_pool` which evaluates whether or not the proxy is
    okay to use after it has been dequeud from the pool.

    [!] IMPORTANT:
    -------------
    We should rely less on the value of response time and min_req_proxy, if
    the proxy has very good metrics (i.e. is very successful but was used
    a lot or has a higher response time).
    """

    evaluations = ProxyEvaluation(reasons=[])
    limits = config['proxies']['pool']['limits']

    request_eval = evaluate_requests(proxy)
    errors_eval = evaluate_errors(proxy)
    error_rate_eval = evaluate_error_rate(proxy)

    evaluations.merge(request_eval, errors_eval, error_rate_eval)

    # Will Have to be Included in evaluate_from_pool When We Start Manually Calculating
    if limits.get('resp_time'):
        if proxy.avg_resp_time > limits['resp_time']:
            reason = AttributeEvaluation(
                value=proxy.avg_resp_time,
                relative_value=limits['resp_time'],
                name="Avg. Response Time",
            )
            evaluations.add(reason)

    return evaluations
