import pytest

from hlbot.execution.interface import AdapterPosition, PlaceOrderRequest, PositionAction
from hlbot.models.trade import TradeSide

def test_open_long_request():
    request = PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.OPEN, 100)
    assert not request.reduce_only

def test_open_short_request():
    request = PlaceOrderRequest("PONS", TradeSide.SELL, PositionAction.OPEN, 100)
    assert not request.reduce_only

def test_close_long_is_reduce_only():
    request = PlaceOrderRequest("PONS", TradeSide.SELL, PositionAction.CLOSE, 100)
    assert request.reduce_only

def test_close_short_is_reduce_only():
    request = PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.CLOSE, 100)
    assert request.reduce_only

def test_valid_post_only_request():
    request = PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.OPEN, 100, .25, True)
    assert request.post_only

def test_post_only_requires_price():
    with pytest.raises(ValueError):
        PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.OPEN, 100, post_only=True)

def test_invalid_notional():
    with pytest.raises(ValueError):
        PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.OPEN, 0)

def test_position_direction():
    assert AdapterPosition("PONS", 2, 100, 5).direction == "long"
    assert AdapterPosition("PONS", -2, 100, 5).direction == "short"
    assert AdapterPosition("PONS", 0, None, 0).direction == "flat"