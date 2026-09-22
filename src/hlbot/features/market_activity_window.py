from collections import defaultdict, deque
from dataclasses import dataclass
from math import sqrt

from hlbot.features.market_activity import MarketActivity

@dataclass(frozen=True)
class RollingMarketActivity:
    ts: float
    dex: str
    coin: str
    active: bool
    day_notional_volume: float
    volume_1m: float
    volume_5m: float
    volume_15m: float
    volume_acceleration_5m: float | None
    oi_notional_return_5m: float | None
    price_return_5m: float | None
    warm: bool
    realized_volatility_5m: float | None = None
    realized_volatility_15m: float | None = None

class MarketActivityWindow:
    def __init__(self, history_seconds: float = 3600, max_gap_seconds: float = 120):
        if history_seconds < 2100: raise ValueError("history_seconds must be at least 2100")
        if max_gap_seconds <= 0: raise ValueError("max_gap_seconds must be positive")
        self.history_seconds = history_seconds
        self.max_gap_seconds = max_gap_seconds
        self._history: dict[tuple[str, str], deque[MarketActivity]] = defaultdict(deque)

    def update(self, activities: tuple[MarketActivity, ...]) -> tuple[RollingMarketActivity, ...]:
        return tuple(self._update(activity) for activity in activities)

    def _update(self, activity: MarketActivity) -> RollingMarketActivity:
        key = activity.dex, activity.coin
        history = self._history[key]

        if history and activity.ts <= history[-1].ts: raise ValueError(f"non-increasing activity timestamp: {activity.coin}")
        if history and activity.ts - history[-1].ts > self.max_gap_seconds: history.clear()

        history.append(activity)
        cutoff = activity.ts - self.history_seconds
        while history and history[0].ts <= cutoff: history.popleft()

        recent_5m = _between(history, activity.ts - 300, activity.ts)
        recent_15m = _between(history, activity.ts - 900, activity.ts)
        baseline_30m = _between(history, activity.ts - 2100, activity.ts - 300)
        baseline_seconds = sum(row.elapsed_seconds for row in baseline_30m)
        warm = baseline_seconds >= 1800

        volume_5m = _volume(recent_5m)
        baseline_5m = _volume(baseline_30m) / 6 if warm else None

        return RollingMarketActivity(
            ts=activity.ts,
            dex=activity.dex,
            coin=activity.coin,
            active=activity.active,
            day_notional_volume=activity.day_notional_volume,
            volume_1m=max(0.0, activity.day_volume_change_per_minute),
            volume_5m=volume_5m,
            volume_15m=_volume(recent_15m),
            volume_acceleration_5m=_ratio(volume_5m, baseline_5m),
            oi_notional_return_5m=_oi_return(recent_5m),
            price_return_5m=_compound_return(recent_5m),
            warm=warm,
            realized_volatility_5m=_realized_volatility(recent_5m),
            realized_volatility_15m=_realized_volatility(recent_15m)
        )

def _between(history, start: float, end: float) -> tuple[MarketActivity, ...]:
    return tuple(row for row in history if start < row.ts <= end)

def _volume(rows: tuple[MarketActivity, ...]) -> float:
    return sum(max(0.0, row.day_volume_change) for row in rows)

def _ratio(value: float, baseline: float | None) -> float | None:
    return None if baseline is None or baseline <= 0 else value / baseline

def _oi_return(rows: tuple[MarketActivity, ...]) -> float | None:
    if not rows: return None
    first, last = rows[0], rows[-1]
    if first.oi_notional is None or first.oi_notional_change is None or last.oi_notional is None: return None
    start = first.oi_notional - first.oi_notional_change
    return None if start <= 0 else last.oi_notional / start - 1

def _compound_return(rows: tuple[MarketActivity, ...]) -> float | None:
    if not rows or any(row.price_return is None for row in rows): return None
    value = 1.0
    for row in rows: value *= 1 + row.price_return
    return value - 1

def _realized_volatility(rows: tuple[MarketActivity, ...]) -> float | None:
    if not rows or any(row.price_return is None for row in rows): return None
    return sqrt(sum(row.price_return ** 2 for row in rows))