from dataclasses import dataclass
from math import isfinite

from hlbot.backtest.replay import ReplayEquityPoint

@dataclass(frozen=True)
class CapitalPoint:
    timestamp: float
    balance: float
    unrealized_pnl: float
    equity: float

def build_capital_curve(equity_curve: tuple[ReplayEquityPoint, ...], initial_balance: float) -> tuple[CapitalPoint, ...]:
    if not isfinite(initial_balance) or initial_balance <= 0: raise ValueError("initial_balance must be positive and finite")

    return tuple(
        CapitalPoint(
            point.timestamp,
            initial_balance + point.realized_pnl_gross - point.fees_paid,
            point.unrealized_pnl,
            initial_balance + point.net_pnl
        )
        for point in equity_curve
    )

def return_pct(initial_balance: float, final_equity: float) -> float:
    if not isfinite(initial_balance) or initial_balance <= 0: raise ValueError("initial_balance must be positive and finite")
    if not isfinite(final_equity): raise ValueError("final_equity must be finite")
    return (final_equity / initial_balance - 1) * 100

def max_drawdown_pct(curve: tuple[CapitalPoint, ...]) -> float:
    if not curve: return 0.0

    peak = curve[0].equity
    drawdown = 0.0

    for point in curve:
        peak = max(peak, point.equity)
        if peak > 0: drawdown = max(drawdown, (peak - point.equity) / peak * 100)

    return drawdown