from collections.abc import Iterable

from hlbot.models.order_book import OrderBookSnapshot
from hlbot.models.trade import Trade

def find_duplicate_trade_ids(trades: Iterable[Trade]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for trade in trades:
        if trade.trade_id in seen:
            duplicates.add(trade.trade_id)
        else:
            seen.add(trade.trade_id)

    return duplicates

def validate_unique_trade_ids(trades: Iterable[Trade]) -> None:
    duplicates = find_duplicate_trade_ids(trades)

    if duplicates: raise ValueError(f"Duplicate trade IDs detected: {sorted(duplicates)}")

def validate_order_book_sequence(snapshots: Iterable[OrderBookSnapshot],) -> None:
    previous_update_id: int | None = None

    for snapshot in snapshots:
        if (previous_update_id is not None and snapshot.update_id <= previous_update_id):
            raise ValueError("Order book update IDs must increase monotonically")

        previous_update_id = snapshot.update_id


def detect_time_gaps(timestamps: Iterable[float], max_gap_seconds: float) -> list[tuple[float, float, float]]:
    if max_gap_seconds <= 0: raise ValueError("max_gap_seconds must be positive")

    ordered = sorted(timestamps)

    gaps: list[tuple[float, float, float]] = []

    for previous, current in zip(ordered, ordered[1:]):
        gap = current - previous

        if gap > max_gap_seconds:
            gaps.append((previous, current, gap))

    return gaps