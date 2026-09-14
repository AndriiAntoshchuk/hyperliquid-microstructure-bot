import bisect
import random
from dataclasses import dataclass

from hlbot.data.coverage import CoverageSegment, timestamp_has_coverage
from hlbot.features.liquidity import liquidity_within_bps
from hlbot.features.microprice import microprice
from hlbot.features.order_book_imbalance import order_book_imbalance, weighted_order_book_imbalance
from hlbot.features.spread import mid_price, spread_bps
from hlbot.features.trade_flow import rolling_trade_flow_imbalance
from hlbot.features.volatility import volatility
from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade
from hlbot.models.trading_episode import TradingEpisode

DEFAULT_OFFSETS = (-30, -10, -5, -1, 0, 1, 5, 10, 30)
DEFAULT_MAX_SNAPSHOT_AGE = 15.0

@dataclass(frozen=True)
class EventStudyPoint:
    event_ts: float
    offset_seconds: int
    target_ts: float
    market_ts: float
    mid_price: float
    spread_bps: float
    imbalance_1: float
    imbalance_5: float
    weighted_imbalance_5: float
    microprice: float
    trade_flow_5s: float
    volatility_10s: float
    bid_liquidity_10bps: float
    ask_liquidity_10bps: float

def latest_snapshot_before(snapshots: list[OrderBookSnapshot], timestamp: float) -> OrderBookSnapshot | None:
    if not snapshots: return None

    timestamps = [snapshot.exchange_ts for snapshot in snapshots]
    index = bisect.bisect_right(timestamps, timestamp) - 1
    return None if index < 0 else snapshots[index]

def snapshots_in_window(snapshots: list[OrderBookSnapshot], end_ts: float, window_seconds: float) -> list[OrderBookSnapshot]:
    start_ts = end_ts - window_seconds
    return [snapshot for snapshot in snapshots if start_ts < snapshot.exchange_ts <= end_ts]

def capture_market_point(event_ts: float, offset_seconds: int, snapshots: list[OrderBookSnapshot], trades: list[Trade], max_snapshot_age: float = DEFAULT_MAX_SNAPSHOT_AGE) -> EventStudyPoint | None:
    target_ts = event_ts + offset_seconds
    snapshot = latest_snapshot_before(snapshots, target_ts)

    if snapshot is None: return None
    if target_ts - snapshot.exchange_ts > max_snapshot_age: return None

    recent_snapshots = snapshots_in_window(snapshots, target_ts, 10)
    prices = [item.mid_price for item in recent_snapshots]
    bid_liquidity, ask_liquidity = liquidity_within_bps(snapshot, 10)

    return EventStudyPoint(
        event_ts=event_ts,
        offset_seconds=offset_seconds,
        target_ts=target_ts,
        market_ts=snapshot.exchange_ts,
        mid_price=mid_price(snapshot),
        spread_bps=spread_bps(snapshot),
        imbalance_1=order_book_imbalance(snapshot, 1),
        imbalance_5=order_book_imbalance(snapshot, 5),
        weighted_imbalance_5=weighted_order_book_imbalance(snapshot, 5),
        microprice=microprice(snapshot),
        trade_flow_5s=rolling_trade_flow_imbalance(trades, target_ts, 5),
        volatility_10s=volatility(prices),
        bid_liquidity_10bps=bid_liquidity,
        ask_liquidity_10bps=ask_liquidity
    )

def build_event_study(episodes: list[TradingEpisode], snapshots: list[OrderBookSnapshot], trades: list[Trade], offsets: tuple[int, ...] = DEFAULT_OFFSETS, max_snapshot_age: float = DEFAULT_MAX_SNAPSHOT_AGE) -> dict[float, list[EventStudyPoint]]:
    snapshots = sorted(snapshots, key=lambda snapshot: snapshot.exchange_ts)
    trades = sorted(trades, key=lambda trade: trade.exchange_ts)
    result = {}

    for episode in episodes:
        points = []

        for offset in offsets:
            point = capture_market_point(episode.start_ts, offset, snapshots, trades, max_snapshot_age)
            if point is not None: points.append(point)

        result[episode.start_ts] = points

    return result

def sample_inactive_times(episodes: list[TradingEpisode], snapshots: list[OrderBookSnapshot], count: int, exclusion_seconds: float = 60, seed: int = 42, coverage_segments: list[CoverageSegment] | None = None, coverage_margin_seconds: float = 30) -> list[float]:
    if count <= 0: raise ValueError("count must be positive")
    if exclusion_seconds < 0: raise ValueError("exclusion_seconds cannot be negative")
    if coverage_margin_seconds < 0: raise ValueError("coverage_margin_seconds cannot be negative")
    if not snapshots: return []

    event_times = [episode.start_ts for episode in episodes]
    candidates = []

    for snapshot in snapshots:
        timestamp = snapshot.exchange_ts

        if coverage_segments is not None and not timestamp_has_coverage(timestamp, coverage_segments, coverage_margin_seconds): continue
        if any(abs(timestamp - event_ts) <= exclusion_seconds for event_ts in event_times): continue

        candidates.append(timestamp)

    if not candidates: return []

    rng = random.Random(seed)
    count = min(count, len(candidates))
    return sorted(rng.sample(candidates, count))