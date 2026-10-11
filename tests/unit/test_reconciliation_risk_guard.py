from types import SimpleNamespace

from hlbot.risk.engine import RiskEngine
from hlbot.risk.models import RiskContext, RiskLimits, RiskViolation

def context(reconciliation_healthy=True):
    return RiskContext(
        timestamp=100,
        market_data_ts=99.5,
        equity=10000,
        peak_equity=10000,
        realized_pnl_today=0,
        current_position_notional=0,
        spread_bps=2,
        volatility_10s=.001,
        open_orders=0,
        reconciliation_healthy=reconciliation_healthy
    )

def test_reconciliation_mismatch_blocks_execution():
    engine = RiskEngine(RiskLimits(
        max_order_notional=500,
        max_position_notional=1000
    ))
    order = SimpleNamespace(
        notional=100,
        increases_exposure=True
    )

    decision = engine.evaluate(order, context(False))

    assert not decision.approved
    assert RiskViolation.RECONCILIATION_MISMATCH in decision.violations

def test_healthy_reconciliation_does_not_add_violation():
    engine = RiskEngine(RiskLimits(
        max_order_notional=500,
        max_position_notional=1000
    ))
    order = SimpleNamespace(
        notional=100,
        increases_exposure=True
    )

    decision = engine.evaluate(order, context())

    assert RiskViolation.RECONCILIATION_MISMATCH not in decision.violations