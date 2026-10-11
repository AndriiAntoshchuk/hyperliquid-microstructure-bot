from dataclasses import dataclass
from statistics import median


MarketKey = tuple[str, str]

@dataclass(frozen=True)
class StableSelectionConfig:
    window_seconds: float = 21600
    epoch_seconds: float = 21600
    entry_rank: int = 20
    retention_rank: int = 30
    trading_rank: int = 10
    min_collection_age_seconds: float = 3600
    score_weight: float = 0.7
    persistence_weight: float = 0.3

    def __post_init__(self):
        if self.window_seconds <= 0 or self.epoch_seconds <= 0: raise ValueError("window/epoch must be positive")
        if self.entry_rank <= 0 or self.trading_rank <= 0: raise ValueError("ranks must be positive")
        if self.retention_rank < self.entry_rank: raise ValueError("retention_rank must be >= entry_rank")
        if self.min_collection_age_seconds < 0: raise ValueError("collection age cannot be negative")
        if self.score_weight < 0 or self.persistence_weight < 0: raise ValueError("weights cannot be negative")
        if self.score_weight + self.persistence_weight <= 0: raise ValueError("weights cannot both be zero")

@dataclass(frozen=True)
class AggregatedMarket:
    dex: str
    coin: str
    rank: int
    aggregate_score: float
    median_score: float
    median_rank: float
    persistence: float
    observations: int
    snapshots: int

@dataclass(frozen=True)
class CollectionMember:
    dex: str
    coin: str
    rank: int
    aggregate_score: float
    median_score: float
    median_rank: float
    persistence: float
    collection_since: float
    warmup_eligible_at: float
    selection_ready: bool

@dataclass(frozen=True)
class StableSelectionPlan:
    epoch_ts: float
    window_start_ts: float
    collection: tuple[CollectionMember, ...]
    trading_candidates: tuple[CollectionMember, ...]

def aggregate_market_selection(snapshots, config=StableSelectionConfig()):
    if not snapshots: return ()

    scores, ranks = {}, {}
    for snapshot in snapshots:
        for rank, row in enumerate(snapshot.candidates, 1):
            key = row.dex, row.coin
            scores.setdefault(key, []).append(row.score)
            ranks.setdefault(key, []).append(rank)

    total = len(snapshots)
    rows = []

    for key, values in scores.items():
        persistence = len(values) / total
        median_score = median(values)
        median_rank = median(ranks[key])
        score = (
            median_score * config.score_weight +
            persistence * config.persistence_weight
        ) / (config.score_weight + config.persistence_weight)
        rows.append((key, score, median_score, median_rank, persistence, len(values)))

    rows.sort(key=lambda row: (-row[1], row[3], row[0][1]))

    return tuple(
        AggregatedMarket(
            key[0], key[1], rank, score, median_score, median_rank,
            persistence, observations, total
        )
        for rank, (key, score, median_score, median_rank, persistence, observations)
        in enumerate(rows, 1)
    )

def build_stable_selection_plan(markets, epoch_ts, previous_collection_since=None,config=StableSelectionConfig()):
    previous = previous_collection_since or {}
    by_key = {(row.dex, row.coin): row for row in markets}

    selected = {
        (row.dex, row.coin) for row in markets
        if row.rank <= config.entry_rank
    }
    selected |= {
        key for key in previous
        if key in by_key and by_key[key].rank <= config.retention_rank
    }

    collection = []
    for key in selected:
        row = by_key[key]
        since = previous.get(key, epoch_ts)
        eligible_at = since + config.min_collection_age_seconds

        collection.append(CollectionMember(
            row.dex, row.coin, row.rank, row.aggregate_score,
            row.median_score, row.median_rank, row.persistence,
            since, eligible_at,
            row.rank <= config.trading_rank and epoch_ts >= eligible_at
        ))

    collection.sort(key=lambda row: row.rank)
    collection = tuple(collection)

    return StableSelectionPlan(
        epoch_ts,
        epoch_ts - config.window_seconds,
        collection,
        tuple(row for row in collection if row.selection_ready)
    )

def collection_since_map(plan):
    return {
        (row.dex, row.coin): row.collection_since
        for row in plan.collection
    }