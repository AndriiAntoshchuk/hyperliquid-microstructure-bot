import pytest

from hlbot.execution.latency import (
    ExecutionLatencyTracker,
    ExecutionStage,
    summarize_latencies,
)


def completed_trace(tracker: ExecutionLatencyTracker, trace_id: str, start: int = 1_000_000_000):
    tracker.start(trace_id, start)
    tracker.record(trace_id, ExecutionStage.DECISION_CREATED, start + 2_000_000)
    tracker.record(trace_id, ExecutionStage.RISK_APPROVED, start + 3_000_000)
    tracker.record(trace_id, ExecutionStage.ORDER_SUBMITTED, start + 5_000_000)
    tracker.record(trace_id, ExecutionStage.EXCHANGE_ACKNOWLEDGED, start + 15_000_000)
    tracker.record(trace_id, ExecutionStage.FIRST_FILL, start + 25_000_000)

def test_records_complete_execution_trace():
    tracker = ExecutionLatencyTracker()
    completed_trace(tracker, "trace-1")

    metrics = tracker.metrics("trace-1")

    assert metrics.market_to_decision_ms == 2
    assert metrics.decision_to_risk_ms == 1
    assert metrics.risk_to_submit_ms == 2
    assert metrics.submit_to_ack_ms == 10
    assert metrics.ack_to_first_fill_ms == 10
    assert metrics.market_to_ack_ms == 15
    assert metrics.market_to_first_fill_ms == 25

def test_incomplete_trace_returns_none_for_missing_latency():
    tracker = ExecutionLatencyTracker()
    tracker.start("trace-1", 1_000_000_000)
    tracker.record("trace-1", ExecutionStage.DECISION_CREATED, 1_002_000_000)

    metrics = tracker.metrics("trace-1")

    assert metrics.market_to_decision_ms == 2
    assert metrics.market_to_ack_ms is None
    assert metrics.market_to_first_fill_ms is None

def test_duplicate_trace_is_rejected():
    tracker = ExecutionLatencyTracker()
    tracker.start("trace-1", 1_000_000_000)

    with pytest.raises(ValueError):
        tracker.start("trace-1", 2_000_000_000)

def test_duplicate_stage_is_rejected():
    tracker = ExecutionLatencyTracker()
    tracker.start("trace-1", 1_000_000_000)
    tracker.record("trace-1", ExecutionStage.DECISION_CREATED, 1_001_000_000)

    with pytest.raises(ValueError):
        tracker.record("trace-1", ExecutionStage.DECISION_CREATED, 1_002_000_000)

def test_timestamp_cannot_move_backwards():
    tracker = ExecutionLatencyTracker()
    tracker.start("trace-1", 1_000_000_000)
    tracker.record("trace-1", ExecutionStage.DECISION_CREATED, 1_010_000_000)

    with pytest.raises(ValueError):
        tracker.record("trace-1", ExecutionStage.RISK_APPROVED, 1_005_000_000)

def test_unknown_trace_is_rejected():
    tracker = ExecutionLatencyTracker()

    with pytest.raises(KeyError):
        tracker.metrics("missing")

def test_market_received_must_use_start():
    tracker = ExecutionLatencyTracker()
    tracker.start("trace-1", 1_000_000_000)

    with pytest.raises(ValueError):
        tracker.record("trace-1", ExecutionStage.MARKET_RECEIVED, 1_001_000_000)

def test_values_ignore_incomplete_traces():
    tracker = ExecutionLatencyTracker()

    completed_trace(tracker, "complete")

    tracker.start("incomplete", 2_000_000_000)
    tracker.record("incomplete", ExecutionStage.DECISION_CREATED, 2_001_000_000)

    values = tracker.values(
        ExecutionStage.MARKET_RECEIVED,
        ExecutionStage.EXCHANGE_ACKNOWLEDGED
    )

    assert values == (15,)

def test_summary_calculates_latency_distribution():
    summary = summarize_latencies([10, 20, 30, 40, 50])

    assert summary.count == 5
    assert summary.mean_ms == 30
    assert summary.min_ms == 10
    assert summary.p50_ms == 30
    assert summary.p90_ms == 46
    assert summary.p95_ms == 48
    assert summary.p99_ms == pytest.approx(49.6)
    assert summary.max_ms == 50

def test_empty_summary_returns_none():
    tracker = ExecutionLatencyTracker()

    summary = tracker.summary(
        ExecutionStage.ORDER_SUBMITTED,
        ExecutionStage.EXCHANGE_ACKNOWLEDGED
    )

    assert summary is None

def test_invalid_latency_values_are_rejected():
    with pytest.raises(ValueError):
        summarize_latencies([1, -1, 2])