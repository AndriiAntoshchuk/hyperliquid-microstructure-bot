from dataclasses import dataclass
from statistics import mean

from hlbot.backtest.execution_policy import ExecutionMode
from hlbot.backtest.replay import ReplayEquityPoint, ReplayResult

@dataclass(frozen=True)
class PerformanceSummary:
    fills: int
    closed_trades: int
    gross_pnl: float
    fees: float
    maker_fees: float
    taker_fees: float
    net_pnl: float
    win_rate: float
    average_trade_pnl: float
    average_holding_seconds: float
    max_drawdown: float
    turnover_notional: float
    weighted_slippage_bps: float

def max_drawdown(equity_curve: tuple[ReplayEquityPoint, ...]) -> float:
    peak = 0.0
    drawdown = 0.0

    for point in equity_curve:
        peak = max(peak, point.net_pnl)
        drawdown = max(drawdown, peak - point.net_pnl)

    return drawdown

def summarize_replay(result: ReplayResult) -> PerformanceSummary:
    trade_pnls = [trade.net_pnl for trade in result.trades]
    holding_times = [trade.holding_seconds for trade in result.trades]
    wins = sum(pnl > 0 for pnl in trade_pnls)
    turnover = sum(item.fill.filled_notional for item in result.fills)
    maker_fees = sum(item.fee_paid for item in result.fills if item.execution_mode == ExecutionMode.MAKER)
    taker_fees = sum(item.fee_paid for item in result.fills if item.execution_mode == ExecutionMode.TAKER)

    weighted_slippage = 0.0

    if turnover > 0:
        weighted_slippage = sum(item.fill.slippage_bps * item.fill.filled_notional for item in result.fills) / turnover

    return PerformanceSummary(
        fills=len(result.fills),
        closed_trades=len(result.trades),
        gross_pnl=result.total_realized_pnl_gross,
        fees=result.total_fees,
        maker_fees=maker_fees,
        taker_fees=taker_fees,
        net_pnl=result.total_realized_pnl_net,
        win_rate=wins / len(trade_pnls) if trade_pnls else 0.0,
        average_trade_pnl=mean(trade_pnls) if trade_pnls else 0.0,
        average_holding_seconds=mean(holding_times) if holding_times else 0.0,
        max_drawdown=max_drawdown(result.equity_curve),
        turnover_notional=turnover,
        weighted_slippage_bps=weighted_slippage
    )