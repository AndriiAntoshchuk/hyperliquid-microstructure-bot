from dataclasses import dataclass

from hlbot.features.execution_cost import execution_cost
from hlbot.features.execution_quality import ExecutionQuality

@dataclass(frozen=True)
class TradingGateResult:
    notional: float
    cost_bps: float
    movement_cost_ratio: float

def best_tradeable_notional(
    curve,
    realized_volatility,
    minimum_full_rate=0.95,
    minimum_movement_cost_ratio=2,
    fee_bps_per_side=5,
    latency_buffer_bps=0
):
    if realized_volatility is None: return None

    rv_bps = realized_volatility * 10_000
    valid = []

    for point in curve:
        quality = ExecutionQuality(**point["quality"])

        if (
            quality.buy_full_rate < minimum_full_rate or
            quality.sell_full_rate < minimum_full_rate
        ):
            continue

        cost = execution_cost(
            point["notional"],
            quality,
            fee_bps_per_side,
            latency_buffer_bps
        )

        if cost is None or cost.total_bps <= 0: continue

        ratio = rv_bps / cost.total_bps
        if ratio >= minimum_movement_cost_ratio:
            valid.append(TradingGateResult(
                point["notional"],
                cost.total_bps,
                ratio
            ))

    return max(valid, key=lambda row: row.notional) if valid else None