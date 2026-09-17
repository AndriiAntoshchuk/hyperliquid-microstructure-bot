from dataclasses import dataclass
from enum import Enum

class MarginMode(Enum):
    AUTO = "auto"
    CROSS = "cross"
    ISOLATED = "isolated"

@dataclass(frozen=True)
class PerpetualMarketConfig:
    coin: str
    leverage: int
    margin_mode: MarginMode = MarginMode.AUTO

    def __post_init__(self):
        if not self.coin: raise ValueError("coin cannot be empty")
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int) or self.leverage <= 0:
            raise ValueError("leverage must be a positive integer")

@dataclass(frozen=True)
class PerpetualExecutionConfig:
    markets: tuple[PerpetualMarketConfig, ...]

    def __post_init__(self):
        if not self.markets: raise ValueError("at least one market is required")
        coins = [market.coin for market in self.markets]
        if len(coins) != len(set(coins)): raise ValueError("duplicate market configuration")

    def market(self, coin: str) -> PerpetualMarketConfig:
        for market in self.markets:
            if market.coin == coin: return market
        raise KeyError(f"unknown coin: {coin}")