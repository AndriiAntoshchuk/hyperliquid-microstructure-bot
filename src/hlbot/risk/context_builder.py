from math import isfinite

from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.order_tracker import OrderTracker
from hlbot.risk.models import RiskContext

class RiskContextBuilder:
    def __init__(self, account: AccountTracker, orders: OrderTracker):
        self.account = account
        self.orders = orders

    def build(
        self,
        coin: str,
        timestamp: float,
        market_data_ts: float,
        spread_bps: float,
        volatility_10s: float,
        connection_healthy: bool = True,
        execution_latency_ms: float | None = None,
        reconciliation_healthy: bool = True
    ) -> RiskContext:
        if not coin: raise ValueError("coin cannot be empty")
        if not isfinite(timestamp) or timestamp <= 0:
            raise ValueError("timestamp must be positive and finite")

        return RiskContext(
            timestamp=timestamp,
            market_data_ts=market_data_ts,
            equity=self.account.equity,
            peak_equity=self.account.peak_equity,
            realized_pnl_today=self.account.realized_pnl_for_day(timestamp),
            current_position_notional=self.account.position_notional(coin),
            spread_bps=spread_bps,
            volatility_10s=volatility_10s,
            open_orders=self.orders.active_order_count,
            connection_healthy=connection_healthy,
            execution_latency_ms=execution_latency_ms,
            reconciliation_healthy=reconciliation_healthy
        )