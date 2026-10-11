from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from hlbot.strategy.signal import MarketState, SignalDirection

LOOKBACKS = (60, 120, 300)

class PositionLike(Protocol):
    direction: SignalDirection
    entry_price: float
    entry_ts: float
    current_notional: float
    scale_ins_used: int

@dataclass(frozen=True)
class PositionContext:
    timestamp: float
    direction: SignalDirection
    holding_seconds: float
    current_notional: float
    inventory_fraction: float
    remaining_capacity_fraction: float
    scale_ins_used: int
    avg_entry_return_bps: float
    initial_entry_return_bps: float
    mfe_bps: float
    mae_bps: float

    spread_bps: float
    volatility_10s: float
    liquidity_imbalance: float
    visible_imbalance: float

    aligned_imbalance_1: float
    aligned_imbalance_5: float
    aligned_weighted_imbalance_5: float
    aligned_microprice_bps: float
    aligned_trade_flow_5s: float

    return_5s_bps: float
    return_30s_bps: float
    return_60s_bps: float | None
    return_120s_bps: float | None
    return_300s_bps: float | None

    weighted_change_5s: float | None
    weighted_change_30s: float | None
    flow_change_5s: float | None
    flow_change_30s: float | None
    liquidity_change_5s: float | None
    liquidity_change_30s: float | None
    spread_change_5s: float | None
    spread_change_30s: float | None
    volatility_change_5s: float | None
    volatility_change_30s: float | None

def imbalance(bid: float, ask: float) -> float:
    total = bid + ask
    return 0 if total == 0 else (bid - ask) / total

def signed_return_bps(current: float, previous: float, sign: float) -> float:
    return sign * (current / previous - 1) * 10_000

class PositionContextBuilder:
    def __init__(self, max_gap_seconds: float = 2):
        self.max_gap_seconds = max_gap_seconds
        self.states = []
        self.times = []
        self.segments = []
        self.segment = 0
        self.entry_ts = None
        self.initial_entry_price = None
        self.mfe_bps = 0.0
        self.mae_bps = 0.0

    def build(
        self,
        state: MarketState,
        position: PositionLike | None,
        max_position_notional: float
    ) -> PositionContext | None:
        self._append(state)

        if position is None:
            self._reset_position()
            return None

        if max_position_notional <= 0 or not isfinite(max_position_notional):
            raise ValueError("max_position_notional must be positive and finite")

        if self.entry_ts != position.entry_ts:
            self.entry_ts = position.entry_ts
            self.initial_entry_price = position.entry_price
            self.mfe_bps = 0
            self.mae_bps = 0

        sign = 1 if position.direction == SignalDirection.LONG else -1
        initial_return = signed_return_bps(state.mid_price, self.initial_entry_price, sign)
        avg_return = signed_return_bps(state.mid_price, position.entry_price, sign)

        self.mfe_bps = max(self.mfe_bps, initial_return)
        self.mae_bps = min(self.mae_bps, initial_return)

        lag5 = self._lag(state.timestamp, 5)
        lag30 = self._lag(state.timestamp, 30)
        lag60 = self._lag(state.timestamp, 60)
        lag120 = self._lag(state.timestamp, 120)
        lag300 = self._lag(state.timestamp, 300)

        liquidity = imbalance(state.bid_liquidity_10bps, state.ask_liquidity_10bps)
        visible = imbalance(state.bid_visible_notional_5, state.ask_visible_notional_5)
        inventory = position.current_notional / max_position_notional

        return PositionContext(
            timestamp=state.timestamp,
            direction=position.direction,
            holding_seconds=state.timestamp - position.entry_ts,
            current_notional=position.current_notional,
            inventory_fraction=inventory,
            remaining_capacity_fraction=max(0, 1 - inventory),
            scale_ins_used=position.scale_ins_used,
            avg_entry_return_bps=avg_return,
            initial_entry_return_bps=initial_return,
            mfe_bps=self.mfe_bps,
            mae_bps=self.mae_bps,
            spread_bps=state.spread_bps,
            volatility_10s=state.volatility_10s,
            liquidity_imbalance=liquidity * sign,
            visible_imbalance=visible * sign,
            aligned_imbalance_1=state.imbalance_1 * sign,
            aligned_imbalance_5=state.imbalance_5 * sign,
            aligned_weighted_imbalance_5=state.weighted_imbalance_5 * sign,
            aligned_microprice_bps=state.microprice_deviation_bps * sign,
            aligned_trade_flow_5s=state.trade_flow_5s * sign,
            return_5s_bps=state.return_5s * 10_000 * sign,
            return_30s_bps=state.return_30s * 10_000 * sign,
            return_60s_bps=self._return(state, lag60, sign),
            return_120s_bps=self._return(state, lag120, sign),
            return_300s_bps=self._return(state, lag300, sign),
            weighted_change_5s=self._change(state, lag5, "weighted_imbalance_5", sign),
            weighted_change_30s=self._change(state, lag30, "weighted_imbalance_5", sign),
            flow_change_5s=self._change(state, lag5, "trade_flow_5s", sign),
            flow_change_30s=self._change(state, lag30, "trade_flow_5s", sign),
            liquidity_change_5s=self._imbalance_change(state, lag5, sign, False),
            liquidity_change_30s=self._imbalance_change(state, lag30, sign, False),
            spread_change_5s=self._change(state, lag5, "spread_bps"),
            spread_change_30s=self._change(state, lag30, "spread_bps"),
            volatility_change_5s=self._change(state, lag5, "volatility_10s"),
            volatility_change_30s=self._change(state, lag30, "volatility_10s")
        )

    def _append(self, state: MarketState):
        if self.times and state.timestamp < self.times[-1]:
            raise ValueError("market states must be chronological")

        if self.times and state.timestamp - self.times[-1] > self.max_gap_seconds:
            self.segment += 1

        self.states.append(state)
        self.times.append(state.timestamp)
        self.segments.append(self.segment)

        cutoff = state.timestamp - 310
        index = bisect_right(self.times, cutoff) - 1

        if index > 0:
            self.states = self.states[index:]
            self.times = self.times[index:]
            self.segments = self.segments[index:]

    def _lag(self, timestamp: float, seconds: float) -> MarketState | None:
        target = timestamp - seconds
        index = bisect_right(self.times, target) - 1

        if index < 0: return None
        if self.segments[index] != self.segments[-1]: return None
        if target - self.times[index] > self.max_gap_seconds: return None
        return self.states[index]

    @staticmethod
    def _return(current, previous, sign):
        if previous is None: return None
        return signed_return_bps(current.mid_price, previous.mid_price, sign)

    @staticmethod
    def _change(current, previous, name, sign=1):
        if previous is None: return None
        return (getattr(current, name) - getattr(previous, name)) * sign

    @staticmethod
    def _imbalance_change(current, previous, sign, visible):
        if previous is None: return None

        if visible:
            now = imbalance(current.bid_visible_notional_5, current.ask_visible_notional_5)
            old = imbalance(previous.bid_visible_notional_5, previous.ask_visible_notional_5)
        else:
            now = imbalance(current.bid_liquidity_10bps, current.ask_liquidity_10bps)
            old = imbalance(previous.bid_liquidity_10bps, previous.ask_liquidity_10bps)

        return (now - old) * sign

    def _reset_position(self):
        self.entry_ts = None
        self.initial_entry_price = None
        self.mfe_bps = 0
        self.mae_bps = 0