from dataclasses import dataclass
from enum import Enum
from math import isfinite


class RiskViolation(Enum):
    KILL_SWITCH = "kill_switch"
    CONNECTION_UNHEALTHY = "connection_unhealthy"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    STALE_MARKET_DATA = "stale_market_data"
    ORDER_LIMIT = "order_limit"
    POSITION_LIMIT = "position_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    SPREAD_LIMIT = "spread_limit"
    VOLATILITY_LIMIT = "volatility_limit"
    OPEN_ORDER_LIMIT = "open_order_limit"
    LATENCY_LIMIT = "latency_limit"

@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: float
    max_position_notional: float
    max_market_data_age_seconds: float | None = None
    max_daily_loss: float | None = None
    max_drawdown_pct: float | None = None
    max_spread_bps: float | None = None
    max_volatility_10s: float | None = None
    max_open_orders: int | None = None
    max_execution_latency_ms: float | None = None

    def __post_init__(self):
        _positive("max_order_notional", self.max_order_notional)
        _positive("max_position_notional", self.max_position_notional)
        _optional_positive("max_market_data_age_seconds", self.max_market_data_age_seconds)
        _optional_positive("max_daily_loss", self.max_daily_loss)
        _optional_positive("max_drawdown_pct", self.max_drawdown_pct)
        _optional_positive("max_spread_bps", self.max_spread_bps)
        _optional_positive("max_volatility_10s", self.max_volatility_10s)
        _optional_positive("max_execution_latency_ms", self.max_execution_latency_ms)

        if self.max_open_orders is not None and self.max_open_orders < 0:
            raise ValueError("max_open_orders cannot be negative")

@dataclass(frozen=True)
class RiskContext:
    timestamp: float
    market_data_ts: float
    equity: float
    peak_equity: float
    realized_pnl_today: float
    current_position_notional: float
    spread_bps: float
    volatility_10s: float
    open_orders: int
    connection_healthy: bool = True
    execution_latency_ms: float | None = None
    reconciliation_healthy: bool = True

    def __post_init__(self):
        for name in (
            "timestamp",
            "market_data_ts",
            "equity",
            "peak_equity",
            "realized_pnl_today",
            "current_position_notional",
            "spread_bps",
            "volatility_10s"
        ):
            if not isfinite(getattr(self, name)): raise ValueError(f"{name} must be finite")

        if self.timestamp <= 0 or self.market_data_ts <= 0:
            raise ValueError("timestamps must be positive")

        if self.market_data_ts > self.timestamp:
            raise ValueError("market_data_ts cannot be after timestamp")

        if self.equity <= 0 or self.peak_equity <= 0:
            raise ValueError("equity values must be positive")

        if self.current_position_notional < 0:
            raise ValueError("current_position_notional cannot be negative")

        if self.spread_bps < 0 or self.volatility_10s < 0:
            raise ValueError("market metrics cannot be negative")

        if self.open_orders < 0:
            raise ValueError("open_orders cannot be negative")

        if self.execution_latency_ms is not None and (not isfinite(self.execution_latency_ms) or self.execution_latency_ms < 0):
                raise ValueError("execution_latency_ms must be non-negative and finite")

    @property
    def market_data_age_seconds(self) -> float:
        return self.timestamp - self.market_data_ts

    @property
    def drawdown_pct(self) -> float:
        return max(0.0, (self.peak_equity - self.equity) / self.peak_equity * 100)

@dataclass(frozen=True)
class RiskDecision:
    violations: tuple[RiskViolation, ...]

    @property
    def approved(self) -> bool:
        return not self.violations

def _positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0: raise ValueError(f"{name} must be positive and finite")

def _optional_positive(name: str, value: float | None) -> None:
    if value is not None: _positive(name, value)