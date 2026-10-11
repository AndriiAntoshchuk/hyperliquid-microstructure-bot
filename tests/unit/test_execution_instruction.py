import pytest

from hlbot.execution.instruction import PerpetualOrderInstruction, entry_instruction, exit_instruction
from hlbot.execution.interface import PositionAction
from hlbot.models.trade import TradeSide
from hlbot.strategy.order_intent import OrderIntent, OrderIntentType
from hlbot.strategy.signal import SignalDirection

def entry(direction: SignalDirection, notional: float = 100) -> OrderIntent:
    return OrderIntent(
        direction,
        notional,
        OrderIntentType.INITIAL_ENTRY,
        0,
        .8,
        "test"
    )

def test_open_long_is_buy():
    instruction = entry_instruction("PONS", entry(SignalDirection.LONG))

    assert instruction.side == TradeSide.BUY
    assert instruction.action == PositionAction.OPEN
    assert instruction.increases_exposure
    assert not instruction.reduce_only

def test_open_short_is_sell():
    instruction = entry_instruction("PONS", entry(SignalDirection.SHORT))

    assert instruction.side == TradeSide.SELL
    assert instruction.action == PositionAction.OPEN

def test_close_long_is_sell():
    instruction = exit_instruction("PONS", SignalDirection.LONG, 100)

    assert instruction.side == TradeSide.SELL
    assert instruction.action == PositionAction.CLOSE
    assert not instruction.increases_exposure
    assert instruction.reduce_only

def test_close_short_is_buy():
    instruction = exit_instruction("PONS", SignalDirection.SHORT, 100)

    assert instruction.side == TradeSide.BUY
    assert instruction.action == PositionAction.CLOSE

def test_notional_is_not_multiplied_by_leverage():
    instruction = entry_instruction("PONS", entry(SignalDirection.LONG, 1000))

    assert instruction.request().notional == 1000

def test_maker_requires_price():
    with pytest.raises(ValueError, match="requires price"):
        PerpetualOrderInstruction(
            "PONS",
            SignalDirection.LONG,
            PositionAction.OPEN,
            100,
            post_only=True
        )

def test_taker_rejects_limit_price():
    with pytest.raises(ValueError, match="cannot specify price"):
        PerpetualOrderInstruction(
            "PONS",
            SignalDirection.LONG,
            PositionAction.OPEN,
            100,
            price=10
        )

def test_maker_request_preserves_price():
    instruction = entry_instruction(
        "PONS",
        entry(SignalDirection.LONG),
        price=10,
        post_only=True
    )

    request = instruction.request()

    assert request.price == 10
    assert request.post_only
    assert request.side == TradeSide.BUY