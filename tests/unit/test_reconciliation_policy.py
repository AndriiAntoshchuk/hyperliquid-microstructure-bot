import pytest

from hlbot.execution.reconciliation import ReconciliationIssue, ReconciliationIssueType, ReconciliationReport
from hlbot.execution.reconciliation_policy import ReconciliationAction, ReconciliationPolicy

def test_healthy_report_allows_trading():
    decision = ReconciliationPolicy().evaluate(ReconciliationReport(()))

    assert decision.action == ReconciliationAction.CONTINUE
    assert decision.healthy
    assert decision.continue_trading
    assert not decision.block_new_orders
    assert not decision.requires_manual_reconciliation

@pytest.mark.parametrize("kind", list(ReconciliationIssueType))
def test_any_reconciliation_issue_blocks_new_orders(kind):
    report = ReconciliationReport((
        ReconciliationIssue(kind, "test", "mismatch"),
    ))

    decision = ReconciliationPolicy().evaluate(report)

    assert decision.action == ReconciliationAction.BLOCK_NEW_ORDERS
    assert not decision.healthy
    assert not decision.continue_trading
    assert decision.block_new_orders
    assert decision.requires_manual_reconciliation
    assert decision.issues == report.issues