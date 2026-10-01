import bisect

from hlbot.features.liquidity import book_depth_notional, liquidity_within_bps
from hlbot.features.microprice import microprice
from hlbot.features.order_book_imbalance import order_book_imbalance, weighted_order_book_imbalance
from hlbot.features.spread import mid_price, spread_bps
from hlbot.features.trade_flow import trade_flow_imbalance
from hlbot.features.volatility import realized_volatility
from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade
from hlbot.strategy.signal import MarketState

DEFAULT_MAX_SNAPSHOT_AGE = 15.0

def price_return(current_price: float, previous_price: float) -> float:
    if current_price <= 0 or previous_price <= 0: raise ValueError("prices must be positive")
    return current_price / previous_price - 1

class MarketStateBuilder:
    def __init__(self, snapshots: list[OrderBookSnapshot], trades: list[Trade], max_snapshot_age: float = DEFAULT_MAX_SNAPSHOT_AGE):
        if max_snapshot_age <= 0: raise ValueError("max_snapshot_age must be positive")
        self.snapshots = sorted(snapshots, key=lambda snapshot: snapshot.exchange_ts)
        self.trades = sorted(trades, key=lambda trade: trade.exchange_ts)
        self.snapshot_times = [snapshot.exchange_ts for snapshot in self.snapshots]
        self.trade_times = [trade.exchange_ts for trade in self.trades]
        self.max_snapshot_age = max_snapshot_age

    def latest_snapshot_before(self, timestamp: float) -> OrderBookSnapshot | None:
        index = bisect.bisect_right(self.snapshot_times, timestamp) - 1
        return None if index < 0 else self.snapshots[index]

    def valid_snapshot_before(self, timestamp: float) -> OrderBookSnapshot | None:
        snapshot = self.latest_snapshot_before(timestamp)
        if snapshot is None or timestamp - snapshot.exchange_ts > self.max_snapshot_age: return None
        return snapshot

    def snapshots_in_window(self, end_ts: float, window_seconds: float) -> list[OrderBookSnapshot]:
        start = bisect.bisect_right(self.snapshot_times, end_ts - window_seconds)
        end = bisect.bisect_right(self.snapshot_times, end_ts)
        return self.snapshots[start:end]

    def trades_in_window(self, end_ts: float, window_seconds: float) -> list[Trade]:
        start = bisect.bisect_right(self.trade_times, end_ts - window_seconds)
        end = bisect.bisect_right(self.trade_times, end_ts)
        return self.trades[start:end]

    def build(self, timestamp: float) -> MarketState | None:
        current = self.valid_snapshot_before(timestamp)
        snapshot_5s = self.valid_snapshot_before(timestamp - 5)
        snapshot_30s = self.valid_snapshot_before(timestamp - 30)
        if current is None or snapshot_5s is None or snapshot_30s is None: return None

        current_mid = mid_price(current)
        micro = microprice(current)
        recent_prices = [mid_price(snapshot) for snapshot in self.snapshots_in_window(timestamp, 10)]
        recent_trades = self.trades_in_window(timestamp, 5)
        bid_liquidity, ask_liquidity = liquidity_within_bps(current, 10)
        bid_visible, ask_visible = book_depth_notional(current, 5)

        return MarketState(
            timestamp=timestamp,
            mid_price=current_mid,
            spread_bps=spread_bps(current),
            imbalance_1=order_book_imbalance(current, 1),
            imbalance_5=order_book_imbalance(current, 5),
            weighted_imbalance_5=weighted_order_book_imbalance(current, 5),
            microprice_deviation_bps=(micro - current_mid) / current_mid * 10_000,
            trade_flow_5s=trade_flow_imbalance(recent_trades),
            volatility_10s=realized_volatility(recent_prices),
            bid_liquidity_10bps=bid_liquidity,
            ask_liquidity_10bps=ask_liquidity,
            return_5s=price_return(current_mid, mid_price(snapshot_5s)),
            return_30s=price_return(current_mid, mid_price(snapshot_30s)),
            bid_visible_notional_5=bid_visible,
            ask_visible_notional_5=ask_visible
        )

def latest_snapshot_before(snapshots: list[OrderBookSnapshot], timestamp: float) -> OrderBookSnapshot | None:
    return MarketStateBuilder(snapshots, []).latest_snapshot_before(timestamp)

def snapshots_in_window(snapshots: list[OrderBookSnapshot], end_ts: float, window_seconds: float) -> list[OrderBookSnapshot]:
    return MarketStateBuilder(snapshots, []).snapshots_in_window(end_ts, window_seconds)

def valid_snapshot_before(snapshots: list[OrderBookSnapshot], timestamp: float, max_snapshot_age: float) -> OrderBookSnapshot | None:
    return MarketStateBuilder(snapshots, [], max_snapshot_age).valid_snapshot_before(timestamp)

def build_market_state(timestamp: float, snapshots: list[OrderBookSnapshot], trades: list[Trade], max_snapshot_age: float = DEFAULT_MAX_SNAPSHOT_AGE) -> MarketState | None:
    return MarketStateBuilder(snapshots, trades, max_snapshot_age).build(timestamp)