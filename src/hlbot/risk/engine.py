from typing import Protocol

from hlbot.risk.models import RiskContext, RiskDecision, RiskLimits, RiskViolation


class RiskOrder(Protocol):
    notional: float

    @property
    def increases_exposure(self) -> bool: ...

class RiskEngine:
    def __init__(self, limits: RiskLimits):
        self.limits = limits
        self._kill_switch = False

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch

    def activate_kill_switch(self) -> None:
        self._kill_switch = True

    def reset_kill_switch(self) -> None:
        self._kill_switch = False

    def evaluate(self, intent: RiskOrder, context: RiskContext) -> RiskDecision:
        violations = []

        if self._kill_switch:
            violations.append(RiskViolation.KILL_SWITCH)

        if not context.connection_healthy:
            violations.append(RiskViolation.CONNECTION_UNHEALTHY)

        if not context.reconciliation_healthy:
            violations.append(RiskViolation.RECONCILIATION_MISMATCH)

        if self.limits.max_market_data_age_seconds is not None:
            if context.market_data_age_seconds > self.limits.max_market_data_age_seconds:
                violations.append(RiskViolation.STALE_MARKET_DATA)

        if intent.notional > self.limits.max_order_notional:
            violations.append(RiskViolation.ORDER_LIMIT)

        if intent.increases_exposure and context.current_position_notional + intent.notional > self.limits.max_position_notional:
                violations.append(RiskViolation.POSITION_LIMIT)

        if self.limits.max_daily_loss is not None and context.realized_pnl_today <= -self.limits.max_daily_loss:
                violations.append(RiskViolation.DAILY_LOSS_LIMIT)

        if self.limits.max_drawdown_pct is not None and context.drawdown_pct >= self.limits.max_drawdown_pct:
                violations.append(RiskViolation.DRAWDOWN_LIMIT)

        if self.limits.max_spread_bps is not None and context.spread_bps > self.limits.max_spread_bps:
                violations.append(RiskViolation.SPREAD_LIMIT)

        if self.limits.max_volatility_10s is not None and context.volatility_10s > self.limits.max_volatility_10s:
                violations.append(RiskViolation.VOLATILITY_LIMIT)

        if self.limits.max_open_orders is not None and context.open_orders >= self.limits.max_open_orders:
                violations.append(RiskViolation.OPEN_ORDER_LIMIT)

        if self.limits.max_execution_latency_ms is not None and context.execution_latency_ms is not None and context.execution_latency_ms > self.limits.max_execution_latency_ms:
                violations.append(RiskViolation.LATENCY_LIMIT)

        return RiskDecision(tuple(violations))