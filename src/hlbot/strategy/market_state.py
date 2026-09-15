import bisect

from hlbot.features.liquidity import liquidity_within_bps
from hlbot.features.microprice import microprice
from hlbot.features.order_book_imbalance import order_book_imbalance, weighted_order_book_imbalance
from hlbot.features.spread import mid_price, spread_bps
from hlbot.features.trade_flow import rolling_trade_flow_imbalance
from hlbot.features.volatility import volatility
from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade
from hlbot.strategy.signal import MarketState

DEFAULT_MAX_SNAPSHOT_AGE = 15.0

def latest_snapshot_before(snapshots: list[OrderBookSnapshot], timestamp: float) -> OrderBookSnapshot | None:
    if not snapshots: return None

    timestamps = [snapshot.exchange_ts for snapshot in snapshots]
    index = bisect.bisect_right(timestamps, timestamp) - 1
    return None if index < 0 else snapshots[index]

def snapshots_in_window(snapshots: list[OrderBookSnapshot], end_ts: float, window_seconds: float) -> list[OrderBookSnapshot]:
    start_ts = end_ts - window_seconds
    return [snapshot for snapshot in snapshots if start_ts < snapshot.exchange_ts <= end_ts]

def valid_snapshot_before(snapshots: list[OrderBookSnapshot], timestamp: float, max_snapshot_age: float) -> OrderBookSnapshot | None:
    snapshot = latest_snapshot_before(snapshots, timestamp)

    if snapshot is None: return None
    if timestamp - snapshot.exchange_ts > max_snapshot_age: return None

    return snapshot

def price_return(current_price: float, previous_price: float) -> float:
    if current_price <= 0 or previous_price <= 0:
        raise ValueError("prices must be positive")

    return current_price / previous_price - 1

def build_market_state(
    timestamp: float,
    snapshots: list[OrderBookSnapshot],
    trades: list[Trade],
    max_snapshot_age: float = DEFAULT_MAX_SNAPSHOT_AGE
) -> MarketState | None:
    if max_snapshot_age <= 0:
        raise ValueError("max_snapshot_age must be positive")

    snapshots = sorted(snapshots, key=lambda snapshot: snapshot.exchange_ts)
    trades = sorted(trades, key=lambda trade: trade.exchange_ts)

    current = valid_snapshot_before(snapshots, timestamp, max_snapshot_age)
    snapshot_5s = valid_snapshot_before(snapshots, timestamp - 5, max_snapshot_age)
    snapshot_30s = valid_snapshot_before(snapshots, timestamp - 30, max_snapshot_age)

    if current is None or snapshot_5s is None or snapshot_30s is None:
        return None

    current_mid = mid_price(current)
    micro = microprice(current)
    recent_snapshots = snapshots_in_window(snapshots, timestamp, 10)
    recent_prices = [mid_price(snapshot) for snapshot in recent_snapshots]
    bid_liquidity, ask_liquidity = liquidity_within_bps(current, 10)

    return MarketState(
        timestamp=timestamp,
        mid_price=current_mid,
        spread_bps=spread_bps(current),
        imbalance_1=order_book_imbalance(current, 1),
        imbalance_5=order_book_imbalance(current, 5),
        weighted_imbalance_5=weighted_order_book_imbalance(current, 5),
        microprice_deviation_bps=(micro - current_mid) / current_mid * 10_000,
        trade_flow_5s=rolling_trade_flow_imbalance(trades, timestamp, 5),
        volatility_10s=volatility(recent_prices),
        bid_liquidity_10bps=bid_liquidity,
        ask_liquidity_10bps=ask_liquidity,
        return_5s=price_return(current_mid, mid_price(snapshot_5s)),
        return_30s=price_return(current_mid, mid_price(snapshot_30s))
    )