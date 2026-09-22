from dataclasses import dataclass

from hlbot.features.market_activity_window import RollingMarketActivity

MarketKey = tuple[str, str]

@dataclass(frozen=True)
class MarketSelectorConfig:
    top_n: int = 10
    min_features: int = 2
    min_day_notional_volume: float = 10_000_000
    estimated_round_trip_cost: float = 0.001
    min_volatility_cost_ratio: float = 2.0
    volume_weight: float = 0.30
    volume_acceleration_weight: float = 0.35
    oi_weight: float = 0.20
    price_weight: float = 0.15

    def __post_init__(self):
        if self.top_n <= 0: raise ValueError("top_n must be positive")
        if not 1 <= self.min_features <= 4: raise ValueError("min_features must be between 1 and 4")
        if self.min_day_notional_volume < 0: raise ValueError("min_day_notional_volume cannot be negative")
        if self.estimated_round_trip_cost < 0: raise ValueError("estimated_round_trip_cost cannot be negative")
        if self.min_volatility_cost_ratio < 0: raise ValueError("min_volatility_cost_ratio cannot be negative")
        if any(weight < 0 for weight in self.weights): raise ValueError("weights cannot be negative")
        if sum(self.weights) <= 0: raise ValueError("at least one weight must be positive")

    @property
    def weights(self) -> tuple[float, ...]:
        return self.volume_weight, self.volume_acceleration_weight, self.oi_weight, self.price_weight

    @property
    def min_realized_volatility_5m(self) -> float:
        return self.estimated_round_trip_cost * self.min_volatility_cost_ratio

@dataclass(frozen=True)
class MarketCandidate:
    ts: float
    dex: str
    coin: str
    score: float
    volume_rank: float | None
    volume_acceleration_rank: float | None
    oi_activity_rank: float | None
    price_activity_rank: float | None
    available_features: int
    warm: bool

class MarketSelector:
    def __init__(self, config: MarketSelectorConfig = MarketSelectorConfig()):
        self.config = config

    def select(self, rows: tuple[RollingMarketActivity, ...]) -> tuple[MarketCandidate, ...]:
        active = tuple(row for row in rows if self._eligible(row))
        self._validate_unique(active)
        if not active: return ()

        volume = _ranks({_key(row): row.volume_5m for row in active})
        acceleration = _ranks({_key(row): row.volume_acceleration_5m for row in active if row.volume_acceleration_5m is not None})
        oi = _ranks({_key(row): abs(row.oi_notional_return_5m) for row in active if row.oi_notional_return_5m is not None})
        price = _ranks({_key(row): abs(row.price_return_5m) for row in active if row.price_return_5m is not None})

        candidates = tuple(
            candidate
            for row in active
            if (candidate := self._candidate(row, volume, acceleration, oi, price)) is not None
        )
        return tuple(sorted(candidates, key=lambda row: (-row.score, -_volume(active, row), row.coin))[:self.config.top_n])

    def _eligible(self, row: RollingMarketActivity) -> bool:
        if not row.active or row.volume_5m <= 0: return False
        if row.day_notional_volume < self.config.min_day_notional_volume: return False
        if row.realized_volatility_5m is None: return False
        return row.realized_volatility_5m >= self.config.min_realized_volatility_5m

    def _candidate(self, row, volume, acceleration, oi, price) -> MarketCandidate | None:
        key = _key(row)
        ranks = volume.get(key), acceleration.get(key), oi.get(key), price.get(key)
        available = tuple(
            (rank, weight)
            for rank, weight in zip(ranks, self.config.weights)
            if rank is not None and weight > 0
        )
        if len(available) < self.config.min_features: return None

        score = sum(rank * weight for rank, weight in available) / sum(weight for _, weight in available)
        return MarketCandidate(
            row.ts,
            row.dex,
            row.coin,
            score,
            *ranks,
            available_features=len(available),
            warm=row.warm
        )

    @staticmethod
    def _validate_unique(rows: tuple[RollingMarketActivity, ...]) -> None:
        keys = [_key(row) for row in rows]
        if len(keys) != len(set(keys)): raise ValueError("duplicate market in selector input")

def _key(row: RollingMarketActivity) -> MarketKey:
    return row.dex, row.coin

def _ranks(values: dict[MarketKey, float]) -> dict[MarketKey, float]:
    if not values: return {}

    unique = sorted(set(values.values()))
    if len(unique) == 1: return {key: 0.5 for key in values}

    ranks = {value: i / (len(unique) - 1) for i, value in enumerate(unique)}
    return {key: ranks[value] for key, value in values.items()}

def _volume(rows: tuple[RollingMarketActivity, ...], candidate: MarketCandidate) -> float:
    return next(row.volume_5m for row in rows if _key(row) == (candidate.dex, candidate.coin))