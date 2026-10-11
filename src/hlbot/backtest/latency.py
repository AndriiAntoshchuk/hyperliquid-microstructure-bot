from dataclasses import dataclass
from math import isfinite

from hlbot.strategy.engine import StrategyAction

@dataclass(frozen=True)
class ExecutionLatency:
    entry_ms: float = 0.0
    scale_in_ms: float = 0.0
    exit_ms: float = 0.0

    def __post_init__(self):
        for name in ("entry_ms", "scale_in_ms", "exit_ms"):
            value = getattr(self, name)

            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

    def milliseconds_for(self, action: StrategyAction) -> float:
        if action == StrategyAction.ENTER: return self.entry_ms
        if action == StrategyAction.SCALE_IN: return self.scale_in_ms
        if action == StrategyAction.EXIT: return self.exit_ms

        raise ValueError(f"unsupported action for latency: {action}")

    def seconds_for(self, action: StrategyAction) -> float:
        return self.milliseconds_for(action) / 1000

    def arrival_ts(self, signal_ts: float, action: StrategyAction) -> float:
        if not isfinite(signal_ts): raise ValueError("signal_ts must be finite")
        return signal_ts + self.seconds_for(action)

    @classmethod
    def constant(cls, milliseconds: float):
        return cls(
            entry_ms=milliseconds,
            scale_in_ms=milliseconds,
            exit_ms=milliseconds
        )