from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum

from hlbot.execution.instruction import PerpetualOrderInstruction
from hlbot.execution.interface import ExecutionAdapter
from hlbot.execution.order_tracker import OrderTracker
from hlbot.execution.risk_checked import RiskCheckedExecution, RiskCheckedExecutor
from hlbot.risk.models import RiskContext

class ReplacementState(Enum):
    WAITING_FOR_CANCEL = "waiting_for_cancel"
    SUBMITTED = "submitted"
    INVALIDATED = "invalidated"
    FAILED = "failed"

@dataclass(frozen=True)
class ReplacementRecord:
    old_client_order_id: str
    instruction: PerpetualOrderInstruction
    state: ReplacementState
    trace_id: str | None = None
    new_client_order_id: str | None = None
    reason: str = ""

    @property
    def terminal(self) -> bool:
        return self.state != ReplacementState.WAITING_FOR_CANCEL

class ReplacementCoordinator:
    def __init__(
        self,
        adapter: ExecutionAdapter,
        executor: RiskCheckedExecutor,
        orders: OrderTracker,
        context_provider: Callable[[str], RiskContext],
        reconciliation_gate
    ):
        self.adapter = adapter
        self.executor = executor
        self.orders = orders
        self.context_provider = context_provider
        self.reconciliation_gate = reconciliation_gate
        self._records: dict[str, ReplacementRecord] = {}

    def request(self, client_order_id: str, instruction: PerpetualOrderInstruction, trace_id: str | None = None) -> ReplacementRecord:
        if not self.reconciliation_gate.reconciliation_healthy: raise ValueError("replacement requires healthy reconciliation")
        if not self.orders.get(client_order_id).active: raise ValueError("only active orders can be replaced")

        existing = self._records.get(client_order_id)
        if existing is not None and not existing.terminal: raise ValueError(f"replacement already pending: {client_order_id}")

        self.adapter.cancel(client_order_id)
        record = ReplacementRecord(client_order_id, instruction, ReplacementState.WAITING_FOR_CANCEL, trace_id)
        self._records[client_order_id] = record
        return record

    def on_cancelled(self, client_order_id: str) -> ReplacementRecord | None:
        record = self._records.get(client_order_id)
        if record is None or record.state != ReplacementState.WAITING_FOR_CANCEL: return record
        if not self.reconciliation_gate.reconciliation_healthy:
            return self._invalidate(record, "reconciliation became unhealthy before replacement")

        result = self.executor.submit(
            record.instruction,
            self.context_provider(record.instruction.coin),
            record.trace_id
        )
        return self._apply_execution(record, result)

    def invalidate(self, client_order_id: str, reason: str) -> ReplacementRecord | None:
        record = self._records.get(client_order_id)
        if record is None or record.state != ReplacementState.WAITING_FOR_CANCEL: return record
        return self._invalidate(record, reason)

    def get(self, client_order_id: str) -> ReplacementRecord:
        try:
            return self._records[client_order_id]
        except KeyError:
            raise KeyError(f"unknown replacement: {client_order_id}") from None

    def _apply_execution(self, record: ReplacementRecord, result: RiskCheckedExecution) -> ReplacementRecord:
        execution = result.execution_result

        if execution is None:
            updated = replace(record, state=ReplacementState.FAILED, reason="replacement blocked by risk")
        elif not execution.accepted:
            updated = replace(record, state=ReplacementState.FAILED, reason=execution.reason)
        else:
            updated = replace(record, state=ReplacementState.SUBMITTED, new_client_order_id=execution.order_id)

        self._records[record.old_client_order_id] = updated
        return updated

    def _invalidate(self, record: ReplacementRecord, reason: str) -> ReplacementRecord:
        updated = replace(record, state=ReplacementState.INVALIDATED, reason=reason)
        self._records[record.old_client_order_id] = updated
        return updated