from dataclasses import dataclass

from hlbot.data.universe_collector import UniverseMarket

@dataclass(frozen=True)
class MarketActivity:
    ts: float
    dex: str
    coin: str
    active: bool
    elapsed_seconds: float
    day_volume_change: float
    day_volume_return: float | None
    open_interest_change: float
    open_interest_return: float | None
    oi_notional: float | None
    oi_notional_change: float | None
    oi_notional_return: float | None
    day_notional_volume: float
    price_return: float | None

    @property
    def day_volume_change_per_minute(self) -> float:
        return self.day_volume_change * 60 / self.elapsed_seconds

def market_activity(previous: UniverseMarket, current: UniverseMarket) -> MarketActivity:
    if previous.dex != current.dex or previous.coin != current.coin:
        raise ValueError("market identity mismatch")
    if current.ts <= previous.ts: raise ValueError("current timestamp must be newer")

    previous_oi_notional = previous.open_interest_notional
    current_oi_notional = current.open_interest_notional

    return MarketActivity(
        ts=current.ts,
        dex=current.dex,
        coin=current.coin,
        active=current.active,
        elapsed_seconds=current.ts - previous.ts,
        day_volume_change=current.day_notional_volume - previous.day_notional_volume,
        day_volume_return=_return(previous.day_notional_volume, current.day_notional_volume),
        open_interest_change=current.open_interest - previous.open_interest,
        open_interest_return=_return(previous.open_interest, current.open_interest),
        oi_notional=current_oi_notional,
        oi_notional_change=_difference(previous_oi_notional, current_oi_notional),
        oi_notional_return=_return(previous_oi_notional, current_oi_notional),
        day_notional_volume=current.day_notional_volume,
        price_return=_return(previous.mark_price, current.mark_price)
    )

class MarketActivityTracker:
    def __init__(self, max_gap_seconds: float = 120):
        if max_gap_seconds <= 0: raise ValueError("max_gap_seconds must be positive")
        self.max_gap_seconds = max_gap_seconds
        self._previous: dict[tuple[str, str], UniverseMarket] = {}

    def update(self, rows: tuple[UniverseMarket, ...]) -> tuple[MarketActivity, ...]:
        activities = []

        for row in rows:
            key = row.dex, row.coin
            previous = self._previous.get(key)

            if previous is not None and 0 < row.ts - previous.ts <= self.max_gap_seconds:
                activities.append(market_activity(previous, row))

            if previous is None or row.ts >= previous.ts:
                self._previous[key] = row

        return tuple(activities)

def _difference(previous: float | None, current: float | None) -> float | None:
    return None if previous is None or current is None else current - previous

def _return(previous: float | None, current: float | None) -> float | None:
    if previous is None or current is None or previous == 0: return None
    return current / previous - 1