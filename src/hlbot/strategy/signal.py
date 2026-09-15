from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol

class SignalDirection(Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"

@dataclass(frozen=True)
class MarketState:
    timestamp: float
    mid_price: float
    spread_bps: float
    imbalance_1: float
    imbalance_5: float
    weighted_imbalance_5: float
    microprice_deviation_bps: float
    trade_flow_5s: float
    volatility_10s: float
    bid_liquidity_10bps: float
    ask_liquidity_10bps: float
    return_5s: float
    return_30s: float

    def __post_init__(self):
        for name, value in vars(self).items():
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")

        if self.mid_price <= 0:
            raise ValueError("mid_price must be positive")

        if self.spread_bps < 0:
            raise ValueError("spread_bps cannot be negative")

        if self.volatility_10s < 0:
            raise ValueError("volatility_10s cannot be negative")

        if self.bid_liquidity_10bps < 0 or self.ask_liquidity_10bps < 0:
            raise ValueError("liquidity cannot be negative")

@dataclass(frozen=True)
class SignalDecision:
    direction: SignalDirection
    strength: float = 0.0
    reason: str = ""

    def __post_init__(self):
        if not isfinite(self.strength):
            raise ValueError("strength must be finite")

        if not 0 <= self.strength <= 1:
            raise ValueError("strength must be between 0 and 1")

        if self.direction == SignalDirection.NONE and self.strength != 0:
            raise ValueError("NONE signal must have zero strength")

class SignalModel(Protocol):
    def evaluate(self, state: MarketState) -> SignalDecision:
        ...

class NoSignalModel:
    def evaluate(self, state: MarketState) -> SignalDecision:
        return SignalDecision(
            direction=SignalDirection.NONE,
            strength=0.0,
            reason="No calibrated signal model"
        )