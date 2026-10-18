from datetime import UTC, datetime
from pathlib import Path

from hlbot.backtest.capital import CapitalPoint, build_capital_curve
from hlbot.backtest.replay import ReplayResult


def timestamps_to_utc(timestamps):
    return [datetime.fromtimestamp(timestamp, UTC) for timestamp in timestamps]

def drawdown_curve(curve: tuple[CapitalPoint, ...]) -> tuple[float, ...]:
    if not curve: return ()

    peak = curve[0].equity
    result = []

    for point in curve:
        peak = max(peak, point.equity)
        drawdown = (peak - point.equity) / peak * 100 if peak > 0 else 0.0
        result.append(drawdown)

    return tuple(result)

def plot_equity(result: ReplayResult, initial_balance: float, output_path: str | Path):
    import matplotlib.pyplot as plt

    curve = build_capital_curve(result.equity_curve, initial_balance)
    times = timestamps_to_utc(point.timestamp for point in curve)

    figure, axis = plt.subplots()
    axis.plot(times, [point.equity for point in curve], label="Equity")
    axis.plot(times, [point.balance for point in curve], label="Realized balance")
    axis.set_title("Account Equity")
    axis.set_xlabel("Time UTC")
    axis.set_ylabel("USD")
    axis.legend()
    axis.grid(True)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

def plot_pnl(result: ReplayResult, output_path: str | Path):
    import matplotlib.pyplot as plt

    times = timestamps_to_utc(point.timestamp for point in result.equity_curve)
    pnl = [point.net_pnl for point in result.equity_curve]

    figure, axis = plt.subplots()
    axis.plot(times, pnl)
    axis.axhline(0, linewidth=1)
    axis.set_title("Net PnL")
    axis.set_xlabel("Time UTC")
    axis.set_ylabel("USD")
    axis.grid(True)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

def plot_drawdown(result: ReplayResult, initial_balance: float, output_path: str | Path):
    import matplotlib.pyplot as plt

    curve = build_capital_curve(result.equity_curve, initial_balance)
    times = timestamps_to_utc(point.timestamp for point in curve)
    drawdowns = drawdown_curve(curve)

    figure, axis = plt.subplots()
    axis.plot(times, drawdowns)
    axis.set_title("Drawdown")
    axis.set_xlabel("Time UTC")
    axis.set_ylabel("Drawdown %")
    axis.grid(True)
    axis.invert_yaxis()
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)

def save_backtest_charts(result: ReplayResult, initial_balance: float, output_dir: str | Path) -> tuple[Path, Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    equity_path = directory / "equity.png"
    pnl_path = directory / "pnl.png"
    drawdown_path = directory / "drawdown.png"

    plot_equity(result, initial_balance, equity_path)
    plot_pnl(result, pnl_path)
    plot_drawdown(result, initial_balance, drawdown_path)

    return equity_path, pnl_path, drawdown_path