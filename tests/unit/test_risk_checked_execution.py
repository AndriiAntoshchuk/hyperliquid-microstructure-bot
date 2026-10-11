import pytest

from hlbot.execution.client import ExecutionResult
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.execution.risk_checked import RiskCheckedExecutor
from hlbot.risk.engine import RiskEngine
from hlbot.risk.models import RiskContext, RiskLimits, RiskViolation
from hlbot.strategy.order_intent import OrderIntent, OrderIntentType
from hlbot.strategy.signal import SignalDirection

class FakeExecutionClient:
    def __init__(self, accepted: bool = True):
        self.accepted = accepted
        self.calls = []
        self.next_id = 1

    def submit(self, intent: OrderIntent) -> ExecutionResult:
        self.calls.append(intent)

        if not self.accepted:
            return ExecutionResult(False, reason="rejected")

        order_id = f"order-{self.next_id}"
        self.next_id += 1
        return ExecutionResult(True, order_id)

def intent(notional: float = 100) -> OrderIntent:
    return OrderIntent(
        SignalDirection.LONG,
        notional,
        OrderIntentType.INITIAL_ENTRY,
        0,
        1.0,
        "test"
    )

def context(**overrides) -> RiskContext:
    values = {
        "timestamp": 100,
        "market_data_ts": 99.5,
        "equity": 10000,
        "peak_equity": 10000,
        "realized_pnl_today": 0,
        "current_position_notional": 0,
        "spread_bps": 2,
        "volatility_10s": .001,
        "open_orders": 0,
        "connection_healthy": True,
        "execution_latency_ms": 50
    }
    values.update(overrides)
    return RiskContext(**values)

def limits(max_open_orders: int = 3) -> RiskLimits:
    return RiskLimits(
        max_order_notional=500,
        max_position_notional=1000,
        max_market_data_age_seconds=2,
        max_daily_loss=200,
        max_drawdown_pct=5,
        max_spread_bps=10,
        max_volatility_10s=.01,
        max_open_orders=max_open_orders,
        max_execution_latency_ms=500
    )

def executor(client=None, risk_limits=None):
    client = client or FakeExecutionClient()
    tracker = OrderTracker()
    result = RiskCheckedExecutor(
        RiskEngine(risk_limits or limits()),
        client,
        tracker
    )
    return result, client, tracker

def test_approved_order_reaches_execution_client():
    execution, client, tracker = executor()

    result = execution.submit(intent(), context())

    assert result.risk_decision.approved
    assert result.submitted
    assert result.execution_result is not None
    assert result.execution_result.accepted
    assert len(client.calls) == 1
    assert tracker.active_order_count == 1

def test_accepted_order_is_created_as_pending():
    execution, _, tracker = executor()

    result = execution.submit(intent(), context())

    order = tracker.get(result.execution_result.order_id)
    assert order.status == OrderStatus.PENDING
    assert order.submitted_ts == 100

def test_rejected_order_never_reaches_execution_client():
    execution, client, tracker = executor()

    result = execution.submit(intent(600), context())

    assert not result.risk_decision.approved
    assert not result.submitted
    assert len(client.calls) == 0
    assert len(tracker) == 0
    assert RiskViolation.ORDER_LIMIT in result.risk_decision.violations

def test_exchange_rejection_is_not_tracked():
    execution, client, tracker = executor(FakeExecutionClient(False))

    result = execution.submit(intent(), context())

    assert result.risk_decision.approved
    assert result.submitted
    assert not result.execution_result.accepted
    assert len(client.calls) == 1
    assert len(tracker) == 0

def test_kill_switch_blocks_execution():
    execution, client, tracker = executor()
    execution.risk_engine.activate_kill_switch()

    result = execution.submit(intent(), context())

    assert not result.submitted
    assert RiskViolation.KILL_SWITCH in result.risk_decision.violations
    assert len(client.calls) == 0
    assert len(tracker) == 0

def test_stale_market_data_blocks_execution():
    execution, client, _ = executor()

    result = execution.submit(intent(), context(market_data_ts=90))

    assert not result.submitted
    assert RiskViolation.STALE_MARKET_DATA in result.risk_decision.violations
    assert len(client.calls) == 0

def test_position_limit_blocks_execution():
    execution, client, _ = executor()

    result = execution.submit(intent(300), context(current_position_notional=800))

    assert not result.submitted
    assert RiskViolation.POSITION_LIMIT in result.risk_decision.violations
    assert len(client.calls) == 0

def test_open_order_limit_uses_tracker_state():
    execution, client, tracker = executor(risk_limits=limits(max_open_orders=1))

    first = execution.submit(intent(), context(open_orders=999))
    second = execution.submit(intent(), context(open_orders=0))

    assert first.submitted
    assert not second.submitted
    assert RiskViolation.OPEN_ORDER_LIMIT in second.risk_decision.violations
    assert len(client.calls) == 1
    assert tracker.active_order_count == 1

def test_apply_exchange_update():
    execution, _, tracker = executor()

    result = execution.submit(intent(), context())
    order_id = result.execution_result.order_id

    execution.apply_update(
        ExecutionOrderState(
            client_order_id=order_id,
            status=OrderStatus.OPEN,
            submitted_ts=100,
            updated_ts=101,
            exchange_order_id="exchange-123"
        )
    )

    order = tracker.get(order_id)
    assert order.status == OrderStatus.OPEN
    assert order.exchange_order_id == "exchange-123"

def test_filled_update_releases_open_order_capacity():
    execution, client, tracker = executor(risk_limits=limits(max_open_orders=1))

    result = execution.submit(intent(), context())
    order_id = result.execution_result.order_id

    execution.apply_update(
        ExecutionOrderState(
            client_order_id=order_id,
            status=OrderStatus.FILLED,
            submitted_ts=100,
            updated_ts=101,
            exchange_order_id="exchange-123",
            filled_quantity=1,
            average_fill_price=100
        )
    )

    second = execution.submit(intent(), context(timestamp=102, market_data_ts=101.5))

    assert second.submitted
    assert tracker.active_order_count == 1
    assert len(client.calls) == 2

def test_accepted_execution_requires_order_id():
    with pytest.raises(ValueError):
        ExecutionResult(True)

def test_rejected_execution_cannot_have_order_id():
    with pytest.raises(ValueError):
        ExecutionResult(False, "order-1", "rejected")