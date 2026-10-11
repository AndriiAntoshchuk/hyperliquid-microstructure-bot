from dataclasses import dataclass
from math import isfinite

from hlbot.backtest.execution_policy import ExecutionMode

@dataclass(frozen=True)
class FeeSchedule:
    taker_bps: float = 0.0
    maker_bps: float = 0.0

    def __post_init__(self):
        if not isfinite(self.taker_bps): raise ValueError("taker_bps must be finite")
        if not isfinite(self.maker_bps): raise ValueError("maker_bps must be finite")
        if self.taker_bps < 0: raise ValueError("taker_bps cannot be negative")

    def bps_for(self, mode: ExecutionMode) -> float:
        if mode == ExecutionMode.TAKER: return self.taker_bps
        if mode == ExecutionMode.MAKER: return self.maker_bps
        raise ValueError(f"unsupported execution mode: {mode}")

    def fee_for(self, notional: float, mode: ExecutionMode) -> float:
        if not isfinite(notional) or notional < 0: raise ValueError("notional must be finite and non-negative")
        return notional * self.bps_for(mode) / 10_000