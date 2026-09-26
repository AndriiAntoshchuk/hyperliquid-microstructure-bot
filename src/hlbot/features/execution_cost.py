from dataclasses import dataclass

from hlbot.features.execution_quality import ExecutionQuality

@dataclass(frozen=True)
class ExecutionCost:
    notional: float
    fill_rate: float
    spread_bps: float
    impact_bps: float
    fees_bps: float
    latency_buffer_bps: float
    total_bps: float

def execution_cost(
    notional: float,
    quality: ExecutionQuality,
    fee_bps_per_side: float = 0,
    latency_buffer_bps: float = 0
):
    impact = quality.round_trip_p90_bps
    if impact is None: return None

    spread = quality.spread_p90_bps
    fees = 2 * fee_bps_per_side

    return ExecutionCost(
        notional=notional,
        fill_rate=min(
            quality.buy_full_rate,
            quality.sell_full_rate
        ),
        spread_bps=spread,
        impact_bps=impact,
        fees_bps=fees,
        latency_buffer_bps=latency_buffer_bps,
        total_bps=spread + impact + fees + latency_buffer_bps
    )