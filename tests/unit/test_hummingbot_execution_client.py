from unittest.mock import Mock

from hlbot.execution.hummingbot_client import HummingbotExecutionClient
from hlbot.execution.instruction import entry_instruction
from hlbot.strategy.order_intent import OrderIntent, OrderIntentType
from hlbot.strategy.signal import SignalDirection

def instruction(price=None, post_only=False):
    intent = OrderIntent(
        SignalDirection.LONG,
        100,
        OrderIntentType.INITIAL_ENTRY,
        0,
        .8,
        "test"
    )
    return entry_instruction("PONS", intent, price, post_only)

def test_taker_submission():
    adapter = Mock()
    adapter.configuration_ready.return_value = True
    adapter.place_taker.return_value = "cid-1"
    client = HummingbotExecutionClient(adapter)

    result = client.submit(instruction())

    assert result.accepted
    assert result.order_id == "cid-1"
    request = adapter.place_taker.call_args.args[0]
    assert request.notional == 100
    adapter.place_maker.assert_not_called()

def test_maker_submission():
    adapter = Mock()
    adapter.configuration_ready.return_value = True
    adapter.place_maker.return_value = "cid-1"
    client = HummingbotExecutionClient(adapter)

    result = client.submit(instruction(10, True))

    assert result.accepted
    assert result.order_id == "cid-1"
    request = adapter.place_maker.call_args.args[0]
    assert request.price == 10
    assert request.post_only
    adapter.place_taker.assert_not_called()

def test_configuration_gate_blocks_submission():
    adapter = Mock()
    adapter.configuration_ready.return_value = False
    client = HummingbotExecutionClient(adapter)

    result = client.submit(instruction())

    assert not result.accepted
    assert "configuration is not ready" in result.reason
    adapter.place_taker.assert_not_called()
    adapter.place_maker.assert_not_called()

def test_adapter_error_becomes_rejected_execution():
    adapter = Mock()
    adapter.configuration_ready.return_value = True
    adapter.place_taker.side_effect = RuntimeError("connector unavailable")
    client = HummingbotExecutionClient(adapter)

    result = client.submit(instruction())

    assert not result.accepted
    assert result.reason == "connector unavailable"