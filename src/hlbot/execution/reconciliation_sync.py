from dataclasses import dataclass
from enum import Enum
from math import isfinite

from hlbot.execution.reconciliation import ReconciliationIssue, ReconciliationReport
from hlbot.execution.reconciliation_policy import ReconciliationPolicy

class ReconciliationSyncState(Enum):
    UNSYNCHRONIZED = "unsynchronized"
    GRACE = "grace"
    READY = "ready"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class ReconciliationSyncDecision:
    state: ReconciliationSyncState
    issues: tuple[ReconciliationIssue, ...] = ()

    @property
    def allow_new_orders(self) -> bool:
        return self.state == ReconciliationSyncState.READY

    @property
    def reconciliation_healthy(self) -> bool:
        return self.allow_new_orders

    @property
    def requires_manual_reconciliation(self) -> bool:
        return self.state == ReconciliationSyncState.BLOCKED

class ReconciliationSyncGate:
    def __init__(
        self,
        grace_seconds: float = 2.0,
        policy: ReconciliationPolicy | None = None
    ):
        if not isfinite(grace_seconds) or grace_seconds < 0:
            raise ValueError("grace_seconds must be non-negative and finite")

        self.grace_seconds = grace_seconds
        self.policy = policy or ReconciliationPolicy()
        self._started_ts: float | None = None
        self._decision = ReconciliationSyncDecision(
            ReconciliationSyncState.UNSYNCHRONIZED
        )

    @property
    def decision(self) -> ReconciliationSyncDecision:
        return self._decision

    @property
    def reconciliation_healthy(self) -> bool:
        return self._decision.reconciliation_healthy

    def begin(self, timestamp: float) -> ReconciliationSyncDecision:
        self._validate_timestamp(timestamp)
        self._started_ts = timestamp
        self._decision = ReconciliationSyncDecision(
            ReconciliationSyncState.GRACE
        )
        return self._decision

    def evaluate(self, timestamp: float, report: ReconciliationReport) -> ReconciliationSyncDecision:
        self._validate_timestamp(timestamp)

        if self._started_ts is None:
            raise ValueError("synchronization has not started")

        if timestamp < self._started_ts:
            raise ValueError("timestamp cannot precede synchronization start")

        if timestamp - self._started_ts < self.grace_seconds:
            self._decision = ReconciliationSyncDecision(
                ReconciliationSyncState.GRACE
            )
            return self._decision

        policy_decision = self.policy.evaluate(report)

        self._decision = ReconciliationSyncDecision(
            ReconciliationSyncState.READY
            if policy_decision.continue_trading
            else ReconciliationSyncState.BLOCKED,
            policy_decision.issues
        )
        return self._decision

    def reset(self) -> None:
        self._started_ts = None
        self._decision = ReconciliationSyncDecision(
            ReconciliationSyncState.UNSYNCHRONIZED
        )

    @staticmethod
    def _validate_timestamp(timestamp: float) -> None:
        if not isfinite(timestamp) or timestamp <= 0:
            raise ValueError("timestamp must be positive and finite")