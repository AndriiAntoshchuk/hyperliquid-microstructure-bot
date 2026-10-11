from collections.abc import Callable
from dataclasses import dataclass, replace

from hlbot.execution.client import ExecutionClient, ExecutionResult
from hlbot.execution.latency import ExecutionLatencyTracker, ExecutionStage
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.risk.engine import RiskEngine
from hlbot.risk.models import RiskContext, RiskDecision
from hlbot.strategy.order_intent import OrderIntent

@dataclass(frozen=True)
class RiskCheckedExecution:
    risk_decision: RiskDecision
    execution_result: ExecutionResult | None
    trace_id: str | None = None

    @property
    def submitted(self) -> bool:
        return self.execution_result is not None

class RiskCheckedExecutor:
    def __init__(
        self,
        risk_engine: RiskEngine,
        client: ExecutionClient,
        tracker: OrderTracker,
        latency: ExecutionLatencyTracker | None = None,
        trace_binder: Callable[[str, str], None] | None = None
    ):
        self.risk_engine = risk_engine
        self.client = client
        self.tracker = tracker
        self.latency = latency
        self.trace_binder = trace_binder

    def submit(self, intent: OrderIntent, context: RiskContext, trace_id: str | None = None) -> RiskCheckedExecution:
        context = replace(context, open_orders=self.tracker.active_order_count)
        decision = self.risk_engine.evaluate(intent, context)

        if not decision.approved:
            return RiskCheckedExecution(decision, None, trace_id)

        self._record(trace_id, ExecutionStage.RISK_APPROVED)
        self._record(trace_id, ExecutionStage.ORDER_SUBMITTED)

        result = self.client.submit(intent)

        if result.accepted:
            self.tracker.add(ExecutionOrderState(
                result.order_id,
                OrderStatus.PENDING,
                context.timestamp,
                context.timestamp
            ))

            if trace_id is not None and self.trace_binder is not None:
                self.trace_binder(result.order_id, trace_id)

        return RiskCheckedExecution(decision, result, trace_id)

    def apply_update(self, order: ExecutionOrderState) -> None:
        self.tracker.update(order)

    def _record(self, trace_id: str | None, stage: ExecutionStage) -> None:
        if trace_id is None: return
        if self.latency is None: raise ValueError("trace_id requires latency tracker")
        self.latency.record(trace_id, stage)