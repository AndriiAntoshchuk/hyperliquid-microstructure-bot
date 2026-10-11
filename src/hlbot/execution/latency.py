from dataclasses import dataclass
from enum import Enum
from math import isfinite
from statistics import mean
from time import perf_counter_ns

class ExecutionStage(Enum):
    MARKET_RECEIVED = "market_received"
    DECISION_CREATED = "decision_created"
    RISK_APPROVED = "risk_approved"
    ORDER_SUBMITTED = "order_submitted"
    EXCHANGE_ACKNOWLEDGED = "exchange_acknowledged"
    FIRST_FILL = "first_fill"

@dataclass(frozen=True)
class LatencyMetrics:
    market_to_decision_ms: float | None
    decision_to_risk_ms: float | None
    risk_to_submit_ms: float | None
    submit_to_ack_ms: float | None
    ack_to_first_fill_ms: float | None
    market_to_ack_ms: float | None
    market_to_first_fill_ms: float | None

@dataclass(frozen=True)
class LatencySummary:
    count: int
    mean_ms: float
    min_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float

class ExecutionLatencyTracker:
    def __init__(self):
        self._traces: dict[str, dict[ExecutionStage, int]] = {}

    def start(self, trace_id: str, timestamp_ns: int | None = None) -> None:
        if not trace_id: raise ValueError("trace_id cannot be empty")
        if trace_id in self._traces: raise ValueError(f"trace already exists: {trace_id}")

        timestamp_ns = self._timestamp(timestamp_ns)
        self._traces[trace_id] = {ExecutionStage.MARKET_RECEIVED: timestamp_ns}

    def record(self, trace_id: str, stage: ExecutionStage, timestamp_ns: int | None = None) -> None:
        trace = self._trace(trace_id)

        if stage == ExecutionStage.MARKET_RECEIVED:
            raise ValueError("MARKET_RECEIVED must be recorded with start()")

        if stage in trace:
            raise ValueError(f"stage already recorded: {stage.value}")

        timestamp_ns = self._timestamp(timestamp_ns)

        if timestamp_ns < max(trace.values()):
            raise ValueError("execution timestamps cannot move backwards")

        trace[stage] = timestamp_ns

    def timestamp_ns(self, trace_id: str, stage: ExecutionStage) -> int | None:
        return self._trace(trace_id).get(stage)

    def latency_ms(self, trace_id: str, start: ExecutionStage, end: ExecutionStage) -> float | None:
        trace = self._trace(trace_id)
        start_ns = trace.get(start)
        end_ns = trace.get(end)

        if start_ns is None or end_ns is None:
            return None

        return (end_ns - start_ns) / 1_000_000

    def metrics(self, trace_id: str) -> LatencyMetrics:
        return LatencyMetrics(
            self.latency_ms(trace_id, ExecutionStage.MARKET_RECEIVED, ExecutionStage.DECISION_CREATED),
            self.latency_ms(trace_id, ExecutionStage.DECISION_CREATED, ExecutionStage.RISK_APPROVED),
            self.latency_ms(trace_id, ExecutionStage.RISK_APPROVED, ExecutionStage.ORDER_SUBMITTED),
            self.latency_ms(trace_id, ExecutionStage.ORDER_SUBMITTED, ExecutionStage.EXCHANGE_ACKNOWLEDGED),
            self.latency_ms(trace_id, ExecutionStage.EXCHANGE_ACKNOWLEDGED, ExecutionStage.FIRST_FILL),
            self.latency_ms(trace_id, ExecutionStage.MARKET_RECEIVED, ExecutionStage.EXCHANGE_ACKNOWLEDGED),
            self.latency_ms(trace_id, ExecutionStage.MARKET_RECEIVED, ExecutionStage.FIRST_FILL)
        )

    def values(self, start: ExecutionStage, end: ExecutionStage) -> tuple[float, ...]:
        values = []

        for trace_id in self._traces:
            value = self.latency_ms(trace_id, start, end)
            if value is not None: values.append(value)

        return tuple(values)

    def summary(self, start: ExecutionStage, end: ExecutionStage) -> LatencySummary | None:
        values = self.values(start, end)
        if not values: return None
        return summarize_latencies(values)

    def _trace(self, trace_id: str) -> dict[ExecutionStage, int]:
        try:
            return self._traces[trace_id]
        except KeyError:
            raise KeyError(f"unknown trace: {trace_id}") from None

    @staticmethod
    def _timestamp(timestamp_ns: int | None) -> int:
        timestamp_ns = perf_counter_ns() if timestamp_ns is None else timestamp_ns

        if not isinstance(timestamp_ns, int) or timestamp_ns <= 0:
            raise ValueError("timestamp_ns must be a positive integer")

        return timestamp_ns

def summarize_latencies(values) -> LatencySummary:
    values = tuple(float(value) for value in values)

    if not values:
        raise ValueError("values cannot be empty")

    if any(not isfinite(value) or value < 0 for value in values):
        raise ValueError("latencies must be non-negative and finite")

    ordered = sorted(values)

    return LatencySummary(
        len(ordered),
        mean(ordered),
        ordered[0],
        _percentile(ordered, .50),
        _percentile(ordered, .90),
        _percentile(ordered, .95),
        _percentile(ordered, .99),
        ordered[-1]
    )

def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1: return values[0]

    index = (len(values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight