from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hlbot.execution.client import ExecutionResult
from hlbot.execution.instruction import exit_instruction
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.execution.replacement import ReplacementCoordinator, ReplacementState
from hlbot.execution.risk_checked import RiskCheckedExecution
from hlbot.risk.models import RiskDecision
from hlbot.strategy.signal import SignalDirection

def tracker():
    orders = OrderTracker()
    orders.add(ExecutionOrderState(
        "old-1",
        OrderStatus.OPEN,
        100,
        101,
        "exchange-1"
    ))
    return orders

def instruction():
    return exit_instruction(
        "PONS",
        SignalDirection.LONG,
        100,
        reason="replace"
    )

def coordinator(healthy=True):
    adapter = Mock()
    executor = Mock()
    orders = tracker()
    context = object()
    provider = Mock(return_value=context)
    gate = SimpleNamespace(reconciliation_healthy=healthy)

    value = ReplacementCoordinator(
        adapter,
        executor,
        orders,
        provider,
        gate
    )
    return value, adapter, executor, provider, gate

def approved(order_id="new-1"):
    return RiskCheckedExecution(
        RiskDecision(()),
        ExecutionResult(True, order_id)
    )

def test_request_cancels_but_does_not_submit():
    replacement, adapter, executor, _, _ = coordinator()

    record = replacement.request("old-1", instruction())

    assert record.state == ReplacementState.WAITING_FOR_CANCEL
    adapter.cancel.assert_called_once_with("old-1")
    executor.submit.assert_not_called()

def test_cancel_confirmation_submits_replacement():
    replacement, _, executor, provider, _ = coordinator()
    new_instruction = instruction()
    executor.submit.return_value = approved()

    replacement.request("old-1", new_instruction)
    record = replacement.on_cancelled("old-1")

    provider.assert_called_once_with("PONS")
    executor.submit.assert_called_once()
    assert record.state == ReplacementState.SUBMITTED
    assert record.new_client_order_id == "new-1"

def test_duplicate_pending_replacement_is_rejected():
    replacement, _, _, _, _ = coordinator()

    replacement.request("old-1", instruction())

    with pytest.raises(ValueError, match="already pending"):
        replacement.request("old-1", instruction())

def test_fill_before_cancel_invalidates_replacement():
    replacement, _, executor, _, _ = coordinator()

    replacement.request("old-1", instruction())
    replacement.invalidate(
        "old-1",
        "order filled before cancellation confirmation"
    )
    record = replacement.on_cancelled("old-1")

    assert record.state == ReplacementState.INVALIDATED
    executor.submit.assert_not_called()

def test_unhealthy_reconciliation_blocks_request():
    replacement, adapter, _, _, _ = coordinator(False)

    with pytest.raises(ValueError, match="healthy reconciliation"):
        replacement.request("old-1", instruction())

    adapter.cancel.assert_not_called()

def test_reconciliation_failure_after_cancel_request_blocks_submission():
    replacement, _, executor, _, gate = coordinator()
    replacement.request("old-1", instruction())

    gate.reconciliation_healthy = False
    record = replacement.on_cancelled("old-1")

    assert record.state == ReplacementState.INVALIDATED
    assert "reconciliation became unhealthy" in record.reason
    executor.submit.assert_not_called()

def test_risk_rejection_marks_replacement_failed():
    replacement, _, executor, _, _ = coordinator()
    executor.submit.return_value = RiskCheckedExecution(
        RiskDecision((Mock(),)),
        None
    )

    replacement.request("old-1", instruction())
    record = replacement.on_cancelled("old-1")

    assert record.state == ReplacementState.FAILED
    assert record.reason == "replacement blocked by risk"

def test_execution_rejection_marks_replacement_failed():
    replacement, _, executor, _, _ = coordinator()
    executor.submit.return_value = RiskCheckedExecution(
        RiskDecision(()),
        ExecutionResult(False, reason="connector rejected")
    )

    replacement.request("old-1", instruction())
    record = replacement.on_cancelled("old-1")

    assert record.state == ReplacementState.FAILED
    assert record.reason == "connector rejected"

def test_terminal_order_cannot_be_replaced():
    replacement, adapter, _, _, _ = coordinator()
    replacement.orders.update(ExecutionOrderState(
        "old-1",
        OrderStatus.CANCELLED,
        100,
        102,
        "exchange-1"
    ))

    with pytest.raises(ValueError, match="active orders"):
        replacement.request("old-1", instruction())

    adapter.cancel.assert_not_called()