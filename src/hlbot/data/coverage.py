from dataclasses import dataclass

from hlbot.models.order_book import OrderBookSnapshot

@dataclass(frozen=True)
class CoverageSegment:
    start_ts: float
    end_ts: float
    snapshots: int

    @property
    def duration(self) -> float:
        return self.end_ts - self.start_ts

def find_coverage_segments(snapshots: list[OrderBookSnapshot], max_gap_seconds: float = 15) -> list[CoverageSegment]:
    if max_gap_seconds <= 0: raise ValueError("max_gap_seconds must be positive")
    if not snapshots: return []

    snapshots = sorted(snapshots, key=lambda snapshot: snapshot.exchange_ts)
    segments = []
    start = snapshots[0].exchange_ts
    previous = snapshots[0].exchange_ts
    count = 1

    for snapshot in snapshots[1:]:
        if snapshot.exchange_ts - previous > max_gap_seconds:
            segments.append(CoverageSegment(start, previous, count))
            start = snapshot.exchange_ts
            count = 1
        else:
            count += 1

        previous = snapshot.exchange_ts

    segments.append(CoverageSegment(start, previous, count))
    return segments

def timestamp_has_coverage(timestamp: float, segments: list[CoverageSegment], margin_seconds: float = 30) -> bool:
    if margin_seconds < 0: raise ValueError("margin_seconds cannot be negative")

    return any(
        segment.start_ts + margin_seconds <= timestamp <= segment.end_ts - margin_seconds
        for segment in segments
    )