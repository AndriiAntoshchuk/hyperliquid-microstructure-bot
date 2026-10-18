from hlbot.execution.instruction import entry_instruction, exit_instruction
from hlbot.risk.engine import RiskEngine
from hlbot.risk.models import RiskContext, RiskLimits, RiskViolation
from hlbot.strategy.order_intent import OrderIntent, OrderIntentType
from hlbot.strategy.signal import SignalDirection


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

def limits() -> RiskLimits:
    return RiskLimits(
        max_order_notional=500,
        max_position_notional=1000,
        max_market_data_age_seconds=2,
        max_daily_loss=200,
        max_drawdown_pct=5,
        max_spread_bps=10,
        max_volatility_10s=.01,
        max_open_orders=3,
        max_execution_latency_ms=500
    )

def test_approves_valid_order():
    decision = RiskEngine(limits()).evaluate(intent(), context())
    assert decision.approved
    assert decision.violations == ()

def test_rejects_order_limit():
    decision = RiskEngine(limits()).evaluate(intent(600), context())
    assert not decision.approved
    assert RiskViolation.ORDER_LIMIT in decision.violations

def test_rejects_position_limit():
    decision = RiskEngine(limits()).evaluate(intent(300), context(current_position_notional=800))
    assert RiskViolation.POSITION_LIMIT in decision.violations

def test_rejects_stale_market_data():
    decision = RiskEngine(limits()).evaluate(intent(), context(market_data_ts=90))
    assert RiskViolation.STALE_MARKET_DATA in decision.violations

def test_rejects_daily_loss():
    decision = RiskEngine(limits()).evaluate(intent(), context(realized_pnl_today=-200))
    assert RiskViolation.DAILY_LOSS_LIMIT in decision.violations

def test_rejects_drawdown():
    decision = RiskEngine(limits()).evaluate(intent(), context(equity=9400, peak_equity=10000))
    assert RiskViolation.DRAWDOWN_LIMIT in decision.violations

def test_rejects_market_conditions():
    decision = RiskEngine(limits()).evaluate(intent(), context(spread_bps=12, volatility_10s=.02))
    assert RiskViolation.SPREAD_LIMIT in decision.violations
    assert RiskViolation.VOLATILITY_LIMIT in decision.violations

def test_rejects_open_order_limit():
    decision = RiskEngine(limits()).evaluate(intent(), context(open_orders=3))
    assert RiskViolation.OPEN_ORDER_LIMIT in decision.violations

def test_rejects_bad_latency():
    decision = RiskEngine(limits()).evaluate(intent(), context(execution_latency_ms=600))
    assert RiskViolation.LATENCY_LIMIT in decision.violations

def test_rejects_unhealthy_connection():
    decision = RiskEngine(limits()).evaluate(intent(), context(connection_healthy=False))
    assert RiskViolation.CONNECTION_UNHEALTHY in decision.violations

def test_kill_switch():
    engine = RiskEngine(limits())
    engine.activate_kill_switch()

    decision = engine.evaluate(intent(), context())

    assert engine.kill_switch_active
    assert RiskViolation.KILL_SWITCH in decision.violations

    engine.reset_kill_switch()
    assert engine.evaluate(intent(), context()).approved

def test_reports_multiple_violations():
    engine = RiskEngine(limits())
    engine.activate_kill_switch()

    decision = engine.evaluate(
        intent(600),
        context(
            market_data_ts=90,
            realized_pnl_today=-300,
            spread_bps=20,
            connection_healthy=False
        )
    )

    assert not decision.approved
    assert len(decision.violations) >= 5

def test_open_order_can_hit_position_limit():
    engine = RiskEngine(limits())
    order = entry_instruction("PONS", intent(200))

    decision = engine.evaluate(
        order,
        context(current_position_notional=900)
    )

    assert RiskViolation.POSITION_LIMIT in decision.violations

def test_close_order_is_not_blocked_by_position_limit():
    engine = RiskEngine(limits())
    order = exit_instruction(
        "PONS",
        SignalDirection.LONG,
        200
    )

    decision = engine.evaluate(
        order,
        context(current_position_notional=900)
    )

    assert RiskViolation.POSITION_LIMIT not in decision.violations