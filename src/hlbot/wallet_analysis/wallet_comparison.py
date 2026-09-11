from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from statistics import mean, median

from hlbot.models.trading_episode import TradingEpisode
from hlbot.wallet_analysis.pnl_analysis import analyze_wallet_performance

@dataclass(frozen=True)
class WalletSummary:
    wallet: str
    number_of_episodes: int
    total_pnl: float
    win_rate: float
    average_duration: float
    median_duration: float
    average_fills_per_episode: float
    median_fills_per_episode: float
    average_max_position_notional: float
    long_episodes: int
    short_episodes: int
    coins: tuple[str, ...]
    active_hours_utc: tuple[int, ...]

@dataclass(frozen=True)
class PairwiseComparison:
    wallet_a: str
    wallet_b: str
    common_coins: tuple[str, ...]
    common_active_hours_utc: tuple[int, ...]

@dataclass(frozen=True)
class MultiWalletComparison:
    wallets: tuple[WalletSummary, ...]
    pairwise: tuple[PairwiseComparison, ...]

def episode_max_position_notional(episode: TradingEpisode) -> float:
    maximum = 0.0

    for fill in episode.fills:
        if fill.start_position is None: continue

        signed_quantity = fill.quantity if fill.side == "buy" else -fill.quantity
        end_position = fill.start_position + signed_quantity

        maximum = max(
            maximum,
            abs(fill.start_position) * fill.price,
            abs(end_position) * fill.price
        )

    return maximum

def summarize_wallet(wallet: str, episodes: list[TradingEpisode]) -> WalletSummary:
    if not episodes:
        return WalletSummary(
            wallet=wallet,
            number_of_episodes=0,
            total_pnl=0,
            win_rate=0,
            average_duration=0,
            median_duration=0,
            average_fills_per_episode=0,
            median_fills_per_episode=0,
            average_max_position_notional=0,
            long_episodes=0,
            short_episodes=0,
            coins=(),
            active_hours_utc=()
        )

    performance = analyze_wallet_performance(episodes)
    durations = [episode.duration for episode in episodes]
    fills_per_episode = [episode.number_of_fills for episode in episodes]
    notionals = [episode_max_position_notional(episode) for episode in episodes]
    hours = {datetime.fromtimestamp(episode.start_ts, tz=timezone.utc).hour for episode in episodes}

    return WalletSummary(
        wallet=wallet,
        number_of_episodes=len(episodes),
        total_pnl=performance.total_pnl,
        win_rate=performance.win_rate,
        average_duration=mean(durations),
        median_duration=median(durations),
        average_fills_per_episode=mean(fills_per_episode),
        median_fills_per_episode=median(fills_per_episode),
        average_max_position_notional=mean(notionals),
        long_episodes=sum(episode.direction == "long" for episode in episodes),
        short_episodes=sum(episode.direction == "short" for episode in episodes),
        coins=tuple(sorted({episode.coin for episode in episodes})),
        active_hours_utc=tuple(sorted(hours))
    )

def compare_wallets(wallet_episodes: dict[str, list[TradingEpisode]]) -> MultiWalletComparison:
    summaries = tuple(summarize_wallet(wallet, episodes) for wallet, episodes in wallet_episodes.items())
    pairwise = []

    for wallet_a, wallet_b in combinations(summaries, 2):
        pairwise.append(
            PairwiseComparison(
                wallet_a=wallet_a.wallet,
                wallet_b=wallet_b.wallet,
                common_coins=tuple(sorted(set(wallet_a.coins) & set(wallet_b.coins))),
                common_active_hours_utc=tuple(sorted(set(wallet_a.active_hours_utc) & set(wallet_b.active_hours_utc)))
            )
        )

    return MultiWalletComparison(wallets=summaries, pairwise=tuple(pairwise))