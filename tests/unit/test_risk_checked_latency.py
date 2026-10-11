from time import perf_counter_ns

import pytest

from hlbot.execution.client import ExecutionResult
from hlbot.execution.latency import ExecutionLatencyTracker, ExecutionStage
from hlbot.execution.order_tracker import OrderTracker
from hlbot.execution.risk_checked import RiskCheckedExecutor
from hlbot.risk.engine import RiskEngine
from hlbot.risk.models import RiskContext, RiskLimits
from hlbot.strategy.order_intent import OrderIntent, OrderIntentType
from hlbot.strategy.signal import SignalDirection

class FakeClient:
    def __init__(self, accepted=True):
        self.accepted = accepted

    def submit(self, intent):
        if self.accepted: return ExecutionResult(True, "order-1")
        return ExecutionResult(False, reason="rejected")

def intent(notional=100):
    return OrderIntent(SignalDirection.LONG, notional, OrderIntentType.INITIAL_ENTRY, 0, 1.0, "test")

def context():
    return RiskContext(100, 99.5, 10000, 10000, 0, 0, 2, .001, 0, True, 50)

def executor(latency=None, accepted=True):
    limits = RiskLimits(500, 1000, max_open_orders=3)
    return RiskCheckedExecutor(RiskEngine(limits), FakeClient(accepted), OrderTracker(), latency)

def start(latency):
    ts = perf_counter_ns()
    latency.start("trace-1", ts)
    latency.record("trace-1", ExecutionStage.DECISION_CREATED, ts + 1)

def test_records_risk_and_submit():
    latency = ExecutionLatencyTracker()
    start(latency)

    result = executor(latency).submit(intent(), context(), "trace-1")

    assert result.submitted
    assert latency.timestamp_ns("trace-1", ExecutionStage.RISK_APPROVED) is not None
    assert latency.timestamp_ns("trace-1", ExecutionStage.ORDER_SUBMITTED) is not None

def test_rejected_risk_records_nothing():
    latency = ExecutionLatencyTracker()
    start(latency)

    result = executor(latency).submit(intent(1000), context(), "trace-1")

    assert not result.submitted
    assert latency.timestamp_ns("trace-1", ExecutionStage.RISK_APPROVED) is None

def test_exchange_rejection_still_counts_submission():
    latency = ExecutionLatencyTracker()
    start(latency)

    result = executor(latency, False).submit(intent(), context(), "trace-1")

    assert result.submitted
    assert not result.execution_result.accepted
    assert latency.timestamp_ns("trace-1", ExecutionStage.ORDER_SUBMITTED) is not None

def test_trace_requires_latency_tracker():
    with pytest.raises(ValueError):
        executor().submit(intent(), context(), "trace-1")

def test_no_trace_still_works():
    assert executor().submit(intent(), context()).submitted