from dataclasses import dataclass
from statistics import mean

from hlbot.models.trading_episode import TradingEpisode
from hlbot.research.event_study import EventStudyPoint

RETURN_EPSILON = 1e-9

@dataclass(frozen=True)
class MomentumObservation:
    event_ts: float
    direction: str
    lookback_seconds: int
    horizon_seconds: int
    pre_return_pct: float
    signed_pre_return_pct: float
    post_return_pct: float
    signed_post_return_pct: float
    entry_style: str

@dataclass(frozen=True)
class MomentumSummary:
    observations: int
    momentum_entries: int
    mean_reversion_entries: int
    neutral_entries: int
    momentum_fraction: float
    mean_reversion_fraction: float
    average_signed_pre_return_pct: float
    average_signed_post_return_pct: float
    momentum_average_post_return_pct: float
    mean_reversion_average_post_return_pct: float

def price_return_pct(start_price: float, end_price: float) -> float:
    if start_price <= 0 or end_price <= 0: raise ValueError("prices must be positive")
    return (end_price / start_price - 1) * 100

def signed_return(return_pct: float, direction: str) -> float:
    if direction == "long": return return_pct
    if direction == "short": return -return_pct
    raise ValueError("direction must be long or short")

def classify_entry_style(signed_pre_return_pct: float, epsilon: float = RETURN_EPSILON) -> str:
    if signed_pre_return_pct > epsilon: return "momentum"
    if signed_pre_return_pct < -epsilon: return "mean_reversion"
    return "neutral"

def point_at_offset(points: list[EventStudyPoint], offset: int) -> EventStudyPoint | None:
    return next((point for point in points if point.offset_seconds == offset), None)

def analyze_episode(episode: TradingEpisode, points: list[EventStudyPoint], lookback_seconds: int = 10, horizon_seconds: int = 10) -> MomentumObservation | None:
    if lookback_seconds <= 0: raise ValueError("lookback_seconds must be positive")
    if horizon_seconds <= 0: raise ValueError("horizon_seconds must be positive")

    before = point_at_offset(points, -lookback_seconds)
    entry = point_at_offset(points, 0)
    after = point_at_offset(points, horizon_seconds)

    if before is None or entry is None or after is None: return None

    pre_return = price_return_pct(before.mid_price, entry.mid_price)
    post_return = price_return_pct(entry.mid_price, after.mid_price)
    signed_pre = signed_return(pre_return, episode.direction)
    signed_post = signed_return(post_return, episode.direction)

    return MomentumObservation(
        event_ts=episode.start_ts,
        direction=episode.direction,
        lookback_seconds=lookback_seconds,
        horizon_seconds=horizon_seconds,
        pre_return_pct=pre_return,
        signed_pre_return_pct=signed_pre,
        post_return_pct=post_return,
        signed_post_return_pct=signed_post,
        entry_style=classify_entry_style(signed_pre)
    )

def analyze_study(episodes: list[TradingEpisode], study: dict[float, list[EventStudyPoint]], lookback_seconds: int = 10, horizon_seconds: int = 10) -> list[MomentumObservation]:
    observations = []

    for episode in episodes:
        points = study.get(episode.start_ts)

        if points is None: continue

        observation = analyze_episode(episode, points, lookback_seconds, horizon_seconds)

        if observation is not None: observations.append(observation)

    return observations

def summarize_observations(observations: list[MomentumObservation]) -> MomentumSummary:
    if not observations:
        return MomentumSummary(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    momentum = [item for item in observations if item.entry_style == "momentum"]
    mean_reversion = [item for item in observations if item.entry_style == "mean_reversion"]
    neutral = [item for item in observations if item.entry_style == "neutral"]
    count = len(observations)

    return MomentumSummary(
        observations=count,
        momentum_entries=len(momentum),
        mean_reversion_entries=len(mean_reversion),
        neutral_entries=len(neutral),
        momentum_fraction=len(momentum) / count,
        mean_reversion_fraction=len(mean_reversion) / count,
        average_signed_pre_return_pct=mean(item.signed_pre_return_pct for item in observations),
        average_signed_post_return_pct=mean(item.signed_post_return_pct for item in observations),
		momentum_average_post_return_pct=mean(item.signed_post_return_pct for item in momentum) if momentum else 0.0,
		mean_reversion_average_post_return_pct=mean(item.signed_post_return_pct for item in mean_reversion) if mean_reversion else 0.0
    )