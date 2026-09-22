from dataclasses import dataclass

from hlbot.data.universe_collector import UniverseMarket
from hlbot.features.market_activity import MarketActivityTracker
from hlbot.features.market_activity_window import MarketActivityWindow, RollingMarketActivity
from hlbot.selection.market_selector import MarketCandidate, MarketSelector, MarketSelectorConfig

@dataclass(frozen=True)
class MarketSelectionSnapshot:
    ts: float
    markets: tuple[RollingMarketActivity, ...]
    candidates: tuple[MarketCandidate, ...]

    @property
    def coins(self) -> tuple[str, ...]:
        return tuple(row.coin for row in self.candidates)

class MarketSelectionEngine:
    def __init__(
        self,
        config: MarketSelectorConfig = MarketSelectorConfig(),
        history_seconds: float = 3600,
        max_gap_seconds: float = 120
    ):
        self.tracker = MarketActivityTracker(max_gap_seconds)
        self.window = MarketActivityWindow(history_seconds, max_gap_seconds)
        self.selector = MarketSelector(config)

    def update(self, rows: tuple[UniverseMarket, ...]) -> MarketSelectionSnapshot:
        if not rows: raise ValueError("universe snapshot cannot be empty")

        ts = rows[0].ts
        if any(row.ts != ts for row in rows): raise ValueError("universe snapshot timestamps must match")

        activities = self.tracker.update(rows)
        markets = self.window.update(activities)
        return MarketSelectionSnapshot(ts, markets, self.selector.select(markets))