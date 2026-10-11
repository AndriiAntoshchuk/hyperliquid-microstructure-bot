import pytest

from hlbot.backtest.execution import SimulatedFill
from hlbot.backtest.performance import max_drawdown, summarize_replay
from hlbot.backtest.replay import ReplayEquityPoint, ReplayFill, ReplayResult, ReplayTrade
from hlbot.models.trade import TradeSide
from hlbot.strategy.engine import StrategyAction
from hlbot.strategy.signal import SignalDirection

def make_fill(notional: float, slippage_bps: float) -> ReplayFill:
    return ReplayFill(
        action=StrategyAction.ENTER,
        fill=SimulatedFill(
            side=TradeSide.BUY,
            timestamp=1000,
            requested_notional=notional,
            filled_notional=notional,
            requested_quantity=None,
            filled_quantity=notional / 100,
            average_price=100,
            reference_mid_price=100,
            slippage_bps=slippage_bps,
            levels_consumed=1,
            fully_filled=True
        )
    )

def make_trade(net_pnl: float, holding_seconds: float) -> ReplayTrade:
    return ReplayTrade(
        direction=SignalDirection.LONG,
        entry_ts=1000,
        exit_ts=1000 + holding_seconds,
        entry_price=100,
        exit_price=101,
        quantity=1,
        gross_pnl=net_pnl,
        fees=0,
        net_pnl=net_pnl,
        scale_ins=0
    )

def test_max_drawdown():
    curve = (
        ReplayEquityPoint(1, 0, 0, 0, 0),
        ReplayEquityPoint(2, 10, 0, 0, 10),
        ReplayEquityPoint(3, 4, 0, 0, 4),
        ReplayEquityPoint(4, 15, 0, 0, 15),
        ReplayEquityPoint(5, 7, 0, 0, 7)
    )

    assert max_drawdown(curve) == pytest.approx(8)

def test_summary_trade_statistics():
    result = ReplayResult(
        fills=(),
        closed_positions=(),
        final_position=None,
        equity_curve=(),
        states_evaluated=0,
        states_skipped=0,
        trades=(
            make_trade(10, 20),
            make_trade(-4, 40)
        )
    )

    summary = summarize_replay(result)

    assert summary.closed_trades == 2
    assert summary.win_rate == pytest.approx(0.5)
    assert summary.average_trade_pnl == pytest.approx(3)
    assert summary.average_holding_seconds == pytest.approx(30)

def test_summary_turnover():
    result = ReplayResult(
        fills=(
            make_fill(100, 10),
            make_fill(300, 20)
        ),
        closed_positions=(),
        final_position=None,
        equity_curve=(),
        states_evaluated=0,
        states_skipped=0
    )

    summary = summarize_replay(result)

    assert summary.turnover_notional == pytest.approx(400)
    assert summary.weighted_slippage_bps == pytest.approx(17.5)

def test_summary_drawdown_uses_equity_curve():
    result = ReplayResult(
        fills=(),
        closed_positions=(),
        final_position=None,
        equity_curve=(
            ReplayEquityPoint(1, 0, 0, 0, 5),
            ReplayEquityPoint(2, 0, 0, 0, -2)
        ),
        states_evaluated=2,
        states_skipped=0
    )

    assert summarize_replay(result).max_drawdown == pytest.approx(7)