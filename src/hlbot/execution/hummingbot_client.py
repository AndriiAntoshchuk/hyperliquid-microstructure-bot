from hlbot.execution.client import ExecutionResult
from hlbot.execution.hummingbot_perpetual_adapter import HummingbotPerpetualAdapter
from hlbot.execution.instruction import PerpetualOrderInstruction

class HummingbotExecutionClient:
    def __init__(self, adapter: HummingbotPerpetualAdapter):
        self.adapter = adapter

    def submit(self, instruction: PerpetualOrderInstruction) -> ExecutionResult:
        if not self.adapter.configuration_ready():
            return ExecutionResult(False, reason="perpetual connector configuration is not ready")

        try:
            request = instruction.request()
            order_id = (
                self.adapter.place_maker(request)
                if instruction.post_only
                else self.adapter.place_taker(request)
            )
        except (KeyError, ValueError, RuntimeError) as exc:
            return ExecutionResult(False, reason=str(exc))

        return ExecutionResult(True, order_id)