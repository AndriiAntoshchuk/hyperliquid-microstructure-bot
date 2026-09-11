import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, median

from hlbot.models.trading_episode import TradingEpisode

@dataclass(frozen=True)
class WalletPerformanceReport:
    total_pnl: float
    number_of_episodes: int
    win_rate: float
    average_pnl: float
    median_pnl: float
    best_pnl: float
    worst_pnl: float
    max_drawdown: float
    longest_losing_streak: int
    top_1_pct_contribution: float | None
    top_5_pct_contribution: float | None
    pnl_without_top_1_pct: float
    pnl_without_top_5_pct: float
    daily_pnl: dict[str, float]
    monthly_pnl: dict[str, float]
    pnl_by_coin: dict[str, float]
    pnl_by_hour_utc: dict[int, float]

def analyze_wallet_performance(episodes: list[TradingEpisode]) -> WalletPerformanceReport:
    if not episodes:
        return WalletPerformanceReport(
            total_pnl=0,
            number_of_episodes=0,
            win_rate=0,
            average_pnl=0,
            median_pnl=0,
            best_pnl=0,
            worst_pnl=0,
            max_drawdown=0,
            longest_losing_streak=0,
            top_1_pct_contribution=None,
            top_5_pct_contribution=None,
            pnl_without_top_1_pct=0,
            pnl_without_top_5_pct=0,
            daily_pnl={},
            monthly_pnl={},
            pnl_by_coin={},
            pnl_by_hour_utc={}
        )

    episodes = sorted(episodes, key=lambda episode: episode.end_ts)
    pnls = [episode.realized_pnl for episode in episodes]
    total_pnl = sum(pnls)

    return WalletPerformanceReport(
        total_pnl=total_pnl,
        number_of_episodes=len(episodes),
        win_rate=sum(pnl > 0 for pnl in pnls) / len(pnls),
        average_pnl=mean(pnls),
        median_pnl=median(pnls),
        best_pnl=max(pnls),
        worst_pnl=min(pnls),
        max_drawdown=calculate_max_drawdown(pnls),
        longest_losing_streak=calculate_longest_losing_streak(pnls),
        top_1_pct_contribution=calculate_top_contribution(pnls, 0.01),
        top_5_pct_contribution=calculate_top_contribution(pnls, 0.05),
        pnl_without_top_1_pct=calculate_pnl_without_top(pnls, 0.01),
        pnl_without_top_5_pct=calculate_pnl_without_top(pnls, 0.05),
        daily_pnl=group_pnl_by_time(episodes, "%Y-%m-%d"),
        monthly_pnl=group_pnl_by_time(episodes, "%Y-%m"),
        pnl_by_coin=group_pnl_by_coin(episodes),
        pnl_by_hour_utc=group_pnl_by_hour(episodes)
    )

def calculate_max_drawdown(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return max_drawdown

def calculate_longest_losing_streak(pnls: list[float]) -> int:
    longest = 0
    current = 0

    for pnl in pnls:
        current = current + 1 if pnl < 0 else 0
        longest = max(longest, current)

    return longest

def calculate_top_contribution(pnls: list[float], fraction: float) -> float | None:
    if not pnls: return None
    total = sum(pnls)
    if total == 0: return None

    count = max(1, math.ceil(len(pnls) * fraction))
    top_pnl = sum(sorted(pnls, reverse=True)[:count])
    return top_pnl / total

def calculate_pnl_without_top(pnls: list[float], fraction: float) -> float:
    if not pnls: return 0

    count = max(1, math.ceil(len(pnls) * fraction))
    return sum(sorted(pnls, reverse=True)[count:])

def group_pnl_by_time(episodes: list[TradingEpisode], format_string: str) -> dict[str, float]:
    result = defaultdict(float)

    for episode in episodes:
        key = datetime.fromtimestamp(episode.end_ts, tz=timezone.utc).strftime(format_string)
        result[key] += episode.realized_pnl

    return dict(sorted(result.items()))

def group_pnl_by_coin(episodes: list[TradingEpisode]) -> dict[str, float]:
    result = defaultdict(float)

    for episode in episodes: result[episode.coin] += episode.realized_pnl
    return dict(sorted(result.items()))

def group_pnl_by_hour(episodes: list[TradingEpisode]) -> dict[int, float]:
    result = defaultdict(float)

    for episode in episodes:
        hour = datetime.fromtimestamp(episode.end_ts, tz=timezone.utc).hour
        result[hour] += episode.realized_pnl

    return dict(sorted(result.items()))