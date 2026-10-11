import pytest

from hlbot.backtest.execution_policy import ExecutionMode, ExecutionPolicy
from hlbot.backtest.fees import FeeSchedule
from hlbot.backtest.latency import ExecutionLatency
from hlbot.backtest.replay import ReplayBacktester
from hlbot.models.order_book import OrderBookLevel, OrderBookSnapshot
from hlbot.models.trade import Trade, TradeSide
from hlbot.strategy.engine import StrategyAction, StrategyEngine
from hlbot.strategy.signal import MarketState, SignalDecision, SignalDirection
from hlbot.strategy.specification import StrategySpec

class TimedSignalModel:
    def __init__(self, long_times=(), short_times=()):
        self.long_times = set(long_times)
        self.short_times = set(short_times)

    def evaluate(self, state: MarketState) -> SignalDecision:
        if state.timestamp in self.long_times: return SignalDecision(SignalDirection.LONG, 1.0, "test long")
        if state.timestamp in self.short_times: return SignalDecision(SignalDirection.SHORT, 1.0, "test short")
        return SignalDecision(SignalDirection.NONE, 0.0, "no signal")

def make_snapshot(timestamp: float, bid: float = 99, ask: float = 101) -> OrderBookSnapshot:
    return OrderBookSnapshot("hyperliquid_perpetual", "PONS-USD", timestamp, timestamp + 0.1, int(timestamp), (OrderBookLevel(bid, 100),), (OrderBookLevel(ask, 100),))

def make_snapshots():
    return [make_snapshot(timestamp) for timestamp in range(1000, 1055, 5)]

def make_spec(max_scale_ins: int = 0, max_holding_seconds: float | None = 10) -> StrategySpec:
    return StrategySpec(base_order_notional=100, max_position_notional=1000, max_scale_ins=max_scale_ins, scale_order_multiplier=1, max_holding_seconds=max_holding_seconds)

def make_trade(timestamp: float, price: float, quantity: float, side: TradeSide, trade_id: str) -> Trade:
    return Trade(trade_id, "hyperliquid_perpetual", "PONS-USD", timestamp, timestamp + 0.1, price, quantity, side)

def test_replay_enters_and_exits_long():
    engine = StrategyEngine(make_spec(), TimedSignalModel(long_times={1030}))
    result = ReplayBacktester(engine).run(make_snapshots(), [])

    assert len(result.fills) == 2
    assert result.fills[0].action == StrategyAction.ENTER
    assert result.fills[1].action == StrategyAction.EXIT
    assert len(result.closed_positions) == 1
    assert result.final_position is None
    assert result.closed_positions[0].realized_pnl_gross == pytest.approx((99 - 101) * (100 / 101))
    assert len(result.equity_curve) == result.states_evaluated
    assert result.equity_curve[-1].unrealized_pnl == 0
    assert result.equity_curve[-1].net_pnl == pytest.approx(result.total_realized_pnl_net)
    assert len(result.trades) == 1

    trade = result.trades[0]
    assert trade.direction == SignalDirection.LONG
    assert trade.entry_ts == 1030
    assert trade.exit_ts == 1040
    assert trade.holding_seconds == pytest.approx(10)
    assert trade.entry_price == pytest.approx(101)
    assert trade.exit_price == pytest.approx(99)
    assert trade.scale_ins == 0
    assert trade.net_pnl == pytest.approx(result.total_realized_pnl_net)

def test_replay_enters_and_exits_short():
    engine = StrategyEngine(make_spec(), TimedSignalModel(short_times={1030}))
    result = ReplayBacktester(engine).run(make_snapshots(), [])

    assert len(result.fills) == 2
    assert result.fills[0].fill.average_price == pytest.approx(99)
    assert result.fills[1].fill.average_price == pytest.approx(101)
    assert result.closed_positions[0].realized_pnl_gross == pytest.approx((99 - 101) * (100 / 99))

def test_replay_supports_scale_in():
    engine = StrategyEngine(make_spec(max_scale_ins=1, max_holding_seconds=None), TimedSignalModel(long_times={1030, 1035}))
    result = ReplayBacktester(engine).run(make_snapshots(), [])

    assert len(result.fills) == 2
    assert result.fills[0].action == StrategyAction.ENTER
    assert result.fills[1].action == StrategyAction.SCALE_IN
    assert result.final_position is not None
    assert result.final_position.quantity == pytest.approx(200 / 101)
    assert result.final_position.average_entry_price == pytest.approx(101)
    assert result.trades == ()

def test_replay_applies_fees():
    engine = StrategyEngine(make_spec(), TimedSignalModel(long_times={1030}))
    result = ReplayBacktester(engine, fee_bps=10).run(make_snapshots(), [])

    assert result.total_fees > 0
    assert result.total_realized_pnl_net < result.total_realized_pnl_gross

def test_replay_skips_missing_market_history():
    snapshots = [make_snapshot(1000), make_snapshot(1005), make_snapshot(1010), make_snapshot(1040)]
    engine = StrategyEngine(make_spec(), TimedSignalModel(long_times={1040}))
    result = ReplayBacktester(engine).run(snapshots, [])

    assert result.states_evaluated == 0
    assert result.states_skipped == 4
    assert len(result.fills) == 0

def test_replay_maker_entry_waits_for_future_trade():
    engine = StrategyEngine(make_spec(), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=10, queue_ahead_fraction=0)
    trades = [make_trade(1032, 99, 2, TradeSide.SELL, "maker-entry")]
    result = ReplayBacktester(engine, execution_policy=policy).run(make_snapshots(), trades)

    assert len(result.fills) == 2
    assert len(result.trades) == 1

    entry = result.fills[0].fill
    assert result.fills[0].action == StrategyAction.ENTER
    assert entry.side == TradeSide.BUY
    assert entry.timestamp == pytest.approx(1032)
    assert entry.average_price == pytest.approx(99)
    assert result.trades[0].entry_ts == pytest.approx(1032)

def test_replay_unfilled_maker_entry_expires():
    engine = StrategyEngine(make_spec(), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=5, queue_ahead_fraction=0)
    result = ReplayBacktester(engine, execution_policy=policy).run(make_snapshots(), [])

    assert result.fills == ()
    assert result.trades == ()
    assert result.final_position is None

def test_replay_partial_maker_entry_survives_expiry():
    engine = StrategyEngine(make_spec(), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=5, queue_ahead_fraction=0)
    trades = [make_trade(1032, 99, 0.5, TradeSide.SELL, "partial-entry")]
    result = ReplayBacktester(engine, execution_policy=policy).run(make_snapshots(), trades)

    assert len(result.fills) == 2
    assert len(result.trades) == 1
    assert result.fills[0].fill.filled_quantity == pytest.approx(0.5)
    assert result.trades[0].entry_ts == pytest.approx(1032)

def test_replay_maker_exit_waits_for_future_trade():
    engine = StrategyEngine(make_spec(max_holding_seconds=5), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy(exit_mode=ExecutionMode.MAKER, maker_max_age_seconds=10, maker_queue_ahead_fraction=0)
    trades = [make_trade(1037, 101, 2, TradeSide.BUY, "maker-exit")]
    result = ReplayBacktester(engine, execution_policy=policy).run(make_snapshots(), trades)

    assert len(result.fills) == 2
    assert len(result.trades) == 1
    assert result.fills[1].fill.side == TradeSide.SELL
    assert result.fills[1].fill.average_price == pytest.approx(101)
    assert result.trades[0].exit_ts == pytest.approx(1037)
    assert result.trades[0].holding_seconds == pytest.approx(7)

def test_replay_uses_separate_maker_and_taker_fees():
    engine = StrategyEngine(make_spec(max_holding_seconds=5), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=10, queue_ahead_fraction=0)
    fees = FeeSchedule(maker_bps=1, taker_bps=10)
    trades = [make_trade(1032, 99, 2, TradeSide.SELL, "maker-entry")]
    result = ReplayBacktester(engine, execution_policy=policy, fee_schedule=fees).run(make_snapshots(), trades)

    assert len(result.fills) == 2
    assert result.fills[0].execution_mode == ExecutionMode.MAKER
    assert result.fills[1].execution_mode == ExecutionMode.TAKER
    assert result.fills[0].fee_paid == pytest.approx(0.01)
    assert result.fills[1].fee_paid == pytest.approx(0.1)
    assert result.total_fees == pytest.approx(0.11)

def test_replay_supports_maker_rebate():
    engine = StrategyEngine(make_spec(max_holding_seconds=5), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=10, queue_ahead_fraction=0)
    fees = FeeSchedule(maker_bps=-1, taker_bps=10)
    trades = [make_trade(1032, 99, 2, TradeSide.SELL, "maker-entry")]
    result = ReplayBacktester(engine, execution_policy=policy, fee_schedule=fees).run(make_snapshots(), trades)

    assert result.fills[0].fee_paid == pytest.approx(-0.01)
    assert result.total_fees == pytest.approx(0.09)

def test_taker_entry_latency_uses_later_snapshot():
    snapshots = make_snapshots()
    snapshots[7] = make_snapshot(1035, bid=109, ask=111)
    engine = StrategyEngine(make_spec(max_holding_seconds=None), TimedSignalModel(long_times={1030}))
    result = ReplayBacktester(engine, latency=ExecutionLatency(entry_ms=200)).run(snapshots, [])

    assert len(result.fills) == 1
    assert result.fills[0].fill.timestamp == pytest.approx(1035)
    assert result.fills[0].fill.average_price == pytest.approx(111)

def test_exit_latency_uses_later_snapshot():
    snapshots = make_snapshots()
    snapshots[9] = make_snapshot(1045, bid=89, ask=91)
    engine = StrategyEngine(make_spec(max_holding_seconds=10), TimedSignalModel(long_times={1030}))
    result = ReplayBacktester(engine, latency=ExecutionLatency(exit_ms=200)).run(snapshots, [])

    assert len(result.fills) == 2
    assert result.fills[0].fill.timestamp == pytest.approx(1030)
    assert result.fills[1].fill.timestamp == pytest.approx(1045)
    assert result.fills[1].fill.average_price == pytest.approx(89)
    assert result.trades[0].holding_seconds == pytest.approx(15)

def test_zero_latency_preserves_same_snapshot_execution():
    engine = StrategyEngine(make_spec(max_holding_seconds=None), TimedSignalModel(long_times={1030}))
    result = ReplayBacktester(engine, latency=ExecutionLatency()).run(make_snapshots(), [])

    assert len(result.fills) == 1
    assert result.fills[0].fill.timestamp == pytest.approx(1030)
    assert result.fills[0].fill.average_price == pytest.approx(101)

def test_maker_latency_places_order_after_arrival():
    snapshots = make_snapshots()
    snapshots[7] = make_snapshot(1035, bid=109, ask=111)
    engine = StrategyEngine(make_spec(max_holding_seconds=None), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=10, queue_ahead_fraction=0)
    trades = [make_trade(1036, 109, 2, TradeSide.SELL, "delayed-maker")]
    result = ReplayBacktester(engine, execution_policy=policy, latency=ExecutionLatency(entry_ms=200)).run(snapshots, trades)

    assert len(result.fills) == 1
    assert result.fills[0].execution_mode == ExecutionMode.MAKER
    assert result.fills[0].fill.timestamp == pytest.approx(1036)
    assert result.fills[0].fill.average_price == pytest.approx(109)

def test_expired_maker_entry_can_reprice_and_fill():
    snapshots = make_snapshots()
    snapshots[7] = make_snapshot(1035, bid=109, ask=111)
    engine = StrategyEngine(make_spec(max_holding_seconds=None), TimedSignalModel(long_times={1030}))
    policy = ExecutionPolicy.maker_entries(max_age_seconds=5, queue_ahead_fraction=0, max_replacements=1)
    trades = [make_trade(1037, 109, 2, TradeSide.SELL, "replacement-fill")]
    result = ReplayBacktester(engine, execution_policy=policy).run(snapshots, trades)

    assert len(result.fills) == 1
    assert result.fills[0].execution_mode == ExecutionMode.MAKER
    assert result.fills[0].fill.timestamp == pytest.approx(1037)
    assert result.fills[0].fill.average_price == pytest.approx(109)
    assert result.final_position is not None