from dataclasses import dataclass

from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection


@dataclass(frozen=True)
class DemoMeanReversionSignal:
    entry_return_5s_bps: float = -30.0

    def __post_init__(self) -> None:
        if self.entry_return_5s_bps >= 0:
            raise ValueError("entry_return_5s_bps must be negative")

    def evaluate(self, state: MarketState) -> SignalDecision:
        observed_bps = state.return_5s * 10_000
        if observed_bps <= self.entry_return_5s_bps:
            return SignalDecision(SignalDirection.LONG, 1.0, "demo past-return mean reversion")
        return SignalDecision(SignalDirection.NONE, 0.0, "threshold not met")
