from typing import Protocol

from hlbot.strategy.rules import ExitDecision, PositionState
from hlbot.strategy.signal import MarketState

class PositionPolicy(Protocol):
    def evaluate(self, state: MarketState, position: PositionState) -> ExitDecision:
        ...