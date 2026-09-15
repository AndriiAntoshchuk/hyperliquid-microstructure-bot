from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class StrategySpec:
    base_order_notional: float
    max_position_notional: float
    max_scale_ins: int
    scale_order_multiplier: float = 1.0
    max_spread_bps: float | None = None
    max_holding_seconds: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None

    def __post_init__(self):
        _require_positive("base_order_notional", self.base_order_notional)
        _require_positive("max_position_notional", self.max_position_notional)
        _require_positive("scale_order_multiplier", self.scale_order_multiplier)

        if self.max_position_notional < self.base_order_notional:
            raise ValueError("max_position_notional must be >= base_order_notional")

        if self.max_scale_ins < 0:
            raise ValueError("max_scale_ins cannot be negative")

        _require_optional_positive("max_spread_bps", self.max_spread_bps)
        _require_optional_positive("max_holding_seconds", self.max_holding_seconds)
        _require_optional_positive("stop_loss_pct", self.stop_loss_pct)
        _require_optional_positive("take_profit_pct", self.take_profit_pct)

    @property
    def max_entry_orders(self) -> int:
        return self.max_scale_ins + 1

def _require_positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")

def _require_optional_positive(name: str, value: float | None) -> None:
    if value is not None:
        _require_positive(name, value)

def scale_order_notional(spec: StrategySpec, scale_index: int) -> float:
    if scale_index < 0:
        raise ValueError("scale_index cannot be negative")

    return spec.base_order_notional * spec.scale_order_multiplier ** scale_index

def remaining_position_capacity(spec: StrategySpec, current_position_notional: float) -> float:
    if not isfinite(current_position_notional) or current_position_notional < 0:
        raise ValueError("current_position_notional must be non-negative and finite")

    return max(0.0, spec.max_position_notional - current_position_notional)

def next_order_notional(spec: StrategySpec, current_position_notional: float, scale_index: int) -> float:
    if scale_index < 0:
        raise ValueError("scale_index cannot be negative")

    if scale_index > spec.max_scale_ins:
        return 0.0

    requested = scale_order_notional(spec, scale_index)
    capacity = remaining_position_capacity(spec, current_position_notional)

    return min(requested, capacity)