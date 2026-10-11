from dataclasses import dataclass
from enum import Enum

from hlbot.execution.reconciliation import ReconciliationIssue, ReconciliationReport

class ReconciliationAction(Enum):
    CONTINUE = "continue"
    BLOCK_NEW_ORDERS = "block_new_orders"

@dataclass(frozen=True)
class ReconciliationDecision:
    action: ReconciliationAction
    issues: tuple[ReconciliationIssue, ...]

    @property
    def healthy(self) -> bool:
        return self.action == ReconciliationAction.CONTINUE

    @property
    def continue_trading(self) -> bool:
        return self.healthy

    @property
    def block_new_orders(self) -> bool:
        return not self.healthy

    @property
    def requires_manual_reconciliation(self) -> bool:
        return not self.healthy

class ReconciliationPolicy:
    def evaluate(self, report: ReconciliationReport) -> ReconciliationDecision:
        action = (
            ReconciliationAction.CONTINUE
            if report.healthy
            else ReconciliationAction.BLOCK_NEW_ORDERS
        )
        return ReconciliationDecision(action, report.issues)