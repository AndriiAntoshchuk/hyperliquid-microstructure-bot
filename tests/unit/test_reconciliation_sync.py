import pytest

from hlbot.execution.reconciliation import (
    ReconciliationIssue,
    ReconciliationIssueType,
    ReconciliationReport,
)
from hlbot.execution.reconciliation_sync import (
    ReconciliationSyncGate,
    ReconciliationSyncState,
)


def healthy_report():
    return ReconciliationReport(())

def unhealthy_report():
    return ReconciliationReport((
        ReconciliationIssue(
            ReconciliationIssueType.EXCHANGE_ORDER_UNKNOWN,
            "cid-1",
            "unknown exchange order"
        ),
    ))

def test_initial_state_blocks_orders():
    gate = ReconciliationSyncGate()

    assert gate.decision.state == ReconciliationSyncState.UNSYNCHRONIZED
    assert not gate.decision.allow_new_orders
    assert not gate.reconciliation_healthy

def test_begin_enters_grace():
    gate = ReconciliationSyncGate(2)

    decision = gate.begin(100)

    assert decision.state == ReconciliationSyncState.GRACE
    assert not decision.allow_new_orders
    assert not decision.requires_manual_reconciliation

def test_healthy_report_during_grace_does_not_enable_trading():
    gate = ReconciliationSyncGate(2)
    gate.begin(100)

    decision = gate.evaluate(101, healthy_report())

    assert decision.state == ReconciliationSyncState.GRACE
    assert not decision.allow_new_orders

def test_healthy_report_after_grace_enables_trading():
    gate = ReconciliationSyncGate(2)
    gate.begin(100)

    decision = gate.evaluate(102, healthy_report())

    assert decision.state == ReconciliationSyncState.READY
    assert decision.allow_new_orders
    assert decision.reconciliation_healthy

def test_unhealthy_report_after_grace_blocks_trading():
    gate = ReconciliationSyncGate(2)
    gate.begin(100)

    decision = gate.evaluate(102, unhealthy_report())

    assert decision.state == ReconciliationSyncState.BLOCKED
    assert not decision.allow_new_orders
    assert decision.requires_manual_reconciliation
    assert len(decision.issues) == 1

def test_reset_returns_to_unsynchronized():
    gate = ReconciliationSyncGate(0)
    gate.begin(100)
    gate.evaluate(100, healthy_report())

    gate.reset()

    assert gate.decision.state == ReconciliationSyncState.UNSYNCHRONIZED
    assert not gate.reconciliation_healthy

def test_evaluate_requires_begin():
    gate = ReconciliationSyncGate()

    with pytest.raises(ValueError, match="has not started"):
        gate.evaluate(100, healthy_report())

def test_timestamp_cannot_precede_sync_start():
    gate = ReconciliationSyncGate()
    gate.begin(100)

    with pytest.raises(ValueError, match="cannot precede"):
        gate.evaluate(99, healthy_report())

def test_zero_grace_can_become_ready_immediately():
    gate = ReconciliationSyncGate(0)
    gate.begin(100)

    decision = gate.evaluate(100, healthy_report())

    assert decision.state == ReconciliationSyncState.READY