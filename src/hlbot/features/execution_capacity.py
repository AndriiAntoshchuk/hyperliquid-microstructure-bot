from dataclasses import dataclass

from hlbot.features.execution_quality import (
    ExecutionQuality,
    analyze_execution_curve
)

@dataclass(frozen=True)
class ExecutionCapacity:
    coin: str
    max_notional: float | None
    minimum_full_rate: float
    curve: tuple[tuple[float, ExecutionQuality], ...]

def analyze_execution_capacity(
    data_dir,
    coin,
    now,
    notionals=(100, 250, 500, 750, 1000, 1500, 2000),
    window_seconds=3600,
    minimum_full_rate=0.95
):
    curve = analyze_execution_curve(
        data_dir,
        coin,
        now,
        notionals,
        window_seconds
    )

    valid = [
        notional
        for notional, quality in curve
        if quality.buy_full_rate >= minimum_full_rate
        and quality.sell_full_rate >= minimum_full_rate
    ]

    return ExecutionCapacity(
        coin,
        max(valid) if valid else None,
        minimum_full_rate,
        curve
    )