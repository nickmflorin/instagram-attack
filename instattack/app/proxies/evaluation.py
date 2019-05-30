from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Any

from instattack.lib.utils import humanize_list


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


def evaluate_errors(proxy, config):

    errors = config['proxies']['pool']['limits'].get('errors', {})

    max_params = [
        ('all', (), ),
        ('connection', ('connection', )),
        ('response', ('response', )),
        ('ssl', ('ssl', )),
        ('timeout', ('timeout', )),
        ('instagram', ('instagram', )),
    ]

    evaluations = ProxyEvaluation(reasons=[])

    for param_set in max_params:
        config_errors = errors.get(param_set[0])
        if config_errors:
            config_active_errors = config_errors.get('active')
            if config_active_errors:
                actual_active_errors = proxy._num_errors(*param_set[1], active=True)

                if actual_active_errors > config_active_errors:
                    reason = AttributeEvaluation(
                        value=actual_active_errors,
                        relative_value=config_active_errors,
                        name=f"{param_set[0]} Active Errors".title(),
                    )
                    evaluations.add(reason)

            config_hist_errors = config_errors.get('historical')
            if config_hist_errors:
                actual_hist_errors = proxy._num_errors(*param_set[1], active=False)

                if actual_hist_errors > config_hist_errors:
                    reason = AttributeEvaluation(
                        value=actual_hist_errors,
                        relative_value=config_hist_errors,
                        name=f"{param_set[0]} Historical Errors".title(),
                    )
                    evaluations.add(reason)
    return evaluations


def evaluate_requests(proxy, config):

    requests = config['proxies']['pool']['limits'].get('requests', {})

    max_params = [
        ('all', (None, ), ),
        ('success', (True, )),
        ('fail', (False, )),
    ]

    evaluations = ProxyEvaluation(reasons=[])

    for param_set in max_params:
        config_requests = requests.get(param_set[0])
        if config_requests:

            config_active_requests = config_requests.get('active')
            if config_active_requests:
                actual_active_requests = proxy._num_requests(active=True, success=param_set[1])

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
                actual_hist_requests = proxy._num_requests(active=False, success=param_set[1])

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


def evaluate_error_rate(proxy, config):

    evaluations = ProxyEvaluation(reasons=[])

    # Not sure why we only need to include the instattack key here?
    config = config['proxies']['pool']['limits']

    if config.get('error_rate'):
        config_error_rate = config['error_rate']
        horizon = config_error_rate.get('horizon')

        config_active_rate = config_error_rate.get('active')
        if config_active_rate:
            actual_active_rate = proxy._error_rate(active=True, horizon=horizon)

            if actual_active_rate > config_active_rate:
                reason = AttributeEvaluation(
                    value=actual_active_rate,
                    relative_value=config_active_rate,
                    name=f"Active Error Rate".title(),
                )
                evaluations.add(reason)

        config_hist_rate = config_error_rate.get('historical')
        if config_hist_rate:
            actual_hist_rate = proxy._error_rate(active=False, horizon=horizon)

            if actual_hist_rate > config_hist_rate:
                reason = AttributeEvaluation(
                    value=actual_hist_rate,
                    relative_value=config_hist_rate,
                    name=f"Historical Error Rate".title(),
                )
                evaluations.add(reason)
    return evaluations


def evaluate_for_pool(proxy, config):
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

    request_eval = evaluate_requests(proxy, config)
    errors_eval = evaluate_errors(proxy, config)
    error_rate_eval = evaluate_error_rate(proxy, config)

    evaluations.merge(request_eval, errors_eval, error_rate_eval)

    config = config['proxies']['pool']['limits']
    evaluations = ProxyEvaluation(reasons=[])

    # Will Have to be Included in evaluate_from_pool When We Start Manually Calculating
    if config.get('resp_time'):
        if proxy.avg_resp_time > config['resp_time']:
            reason = AttributeEvaluation(
                value=actual_hist_requests,
                relative_value=config_hist_requests,
                name="Avg. Response Time".title(),
            )
            evaluations.add(reason)

    return evaluations


def evaluate_from_pool(proxy, config):

    config = config['proxies']['pool']['limits']
    evaluations = ProxyEvaluation(reasons=[])

    request_eval = evaluate_requests(proxy, config)
    errors_eval = evaluate_errors(proxy, config)
    error_rate_eval = evaluate_error_rate(proxy, config)

    if (proxy.active_errors.get('most_recent') and
            proxy.active_errors['most_recent'] == 'too_many_requests'):
        if proxy.time_since_used < config['too_many_requests_delay']:

            reason = AttributeEvaluation(
                value=proxy.time_since_used,
                relative_value=config['too_many_requests_delay'],
                name="Time Between 429 Requests".title(),
                comparison="<"
            )
            evaluations.add(reason)

    return evaluations
