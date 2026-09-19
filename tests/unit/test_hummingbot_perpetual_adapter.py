from decimal import Decimal
from enum import Enum
from types import SimpleNamespace

import pytest

from hlbot.execution.hummingbot_perpetual_adapter import HummingbotPerpetualAdapter
from hlbot.execution.interface import PlaceOrderRequest, PositionAction
from hlbot.execution.perpetual_config import MarginMode, PerpetualExecutionConfig, PerpetualMarketConfig
from hlbot.models.trade import TradeSide

class HBAction(Enum):
    OPEN = "open"
    CLOSE = "close"

class HBMode(Enum):
    ONEWAY = "oneway"

class FakeConnector:
    def __init__(self):
        self.calls = []
        self.position_mode = None
        self.leverages = {}
        self.account_positions = {}
        self.in_flight_orders = {}
        self._balances = {"USDC": Decimal("1000")}

    def set_position_mode(self, mode):
        self.position_mode = mode

    def set_leverage(self, pair, leverage):
        self.leverages[pair] = leverage

    def get_leverage(self, pair):
        return self.leverages.get(pair, 1)

    def get_price(self, pair, is_buy):
        return Decimal("10")

    def quantize_order_amount(self, pair, amount):
        return amount.quantize(Decimal(".01"))

    def quantize_order_price(self, pair, price):
        return price.quantize(Decimal(".001"))

    def buy(self, pair, amount, order_type, price, **kwargs):
        self.calls.append(("buy", pair, amount, order_type, price, kwargs))
        return "buy-1"

    def sell(self, pair, amount, order_type, price, **kwargs):
        self.calls.append(("sell", pair, amount, order_type, price, kwargs))
        return "sell-1"

    def cancel(self, pair, order_id):
        self.calls.append(("cancel", pair, order_id))

    def get_all_balances(self):
        return self._balances

    def get_available_balance(self, asset):
        return self._balances.get(asset, 0)

def adapter(margin_mode=MarginMode.AUTO):
    connector = FakeConnector()
    config = PerpetualExecutionConfig((PerpetualMarketConfig("PONS", 5, margin_mode),))
    execution = HummingbotPerpetualAdapter(
        connector, {"PONS": "PONS-USDC"}, config,
        "MARKET", "MAKER", HBAction.OPEN, HBAction.CLOSE, HBMode.ONEWAY
    )
    return execution, connector

def test_configures_oneway_and_leverage():
    execution, connector = adapter()

    execution.request_configuration()

    assert connector.position_mode == HBMode.ONEWAY
    assert connector.leverages["PONS-USDC"] == 5
    assert execution.configuration_ready()

def test_explicit_margin_mode_not_supported():
    execution, _ = adapter(MarginMode.CROSS)

    with pytest.raises(NotImplementedError):
        execution.request_configuration()

def test_open_long():
    execution, connector = adapter()

    execution.place_taker(PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.OPEN, 100))

    assert connector.calls[0][0] == "buy"
    assert connector.calls[0][-1]["position_action"] == HBAction.OPEN

def test_open_short():
    execution, connector = adapter()

    execution.place_taker(PlaceOrderRequest("PONS", TradeSide.SELL, PositionAction.OPEN, 100))

    assert connector.calls[0][0] == "sell"
    assert connector.calls[0][-1]["position_action"] == HBAction.OPEN

def test_close_long_is_reduce_only_action():
    execution, connector = adapter()

    execution.place_taker(PlaceOrderRequest("PONS", TradeSide.SELL, PositionAction.CLOSE, 100))

    assert connector.calls[0][-1]["position_action"] == HBAction.CLOSE

def test_close_short_is_reduce_only_action():
    execution, connector = adapter()

    execution.place_taker(PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.CLOSE, 100))

    assert connector.calls[0][-1]["position_action"] == HBAction.CLOSE

def test_maker_order():
    execution, connector = adapter()

    execution.place_maker(PlaceOrderRequest(
        "PONS", TradeSide.BUY, PositionAction.OPEN, 95, 9.5, True
    ))

    assert connector.calls[0][3] == "MAKER"
    assert connector.calls[0][4] == Decimal("9.500")

def test_position_translation():
    execution, connector = adapter()
    connector.leverages["PONS-USDC"] = 5
    connector.account_positions["x"] = SimpleNamespace(
        trading_pair="PONS-USDC",
        amount=Decimal("-2"),
        entry_price=Decimal("10"),
        unrealized_pnl=Decimal("3"),
        leverage=Decimal("5")
    )

    position = execution.position("PONS")

    assert position.quantity == -2
    assert position.direction == "short"
    assert position.leverage == 5

def test_cancel():
    execution, connector = adapter()
    order_id = execution.place_taker(
        PlaceOrderRequest("PONS", TradeSide.BUY, PositionAction.OPEN, 100)
    )

    execution.cancel(order_id)

    assert connector.calls[-1] == ("cancel", "PONS-USDC", order_id)

def test_unknown_coin():
    execution, _ = adapter()

    with pytest.raises(KeyError):
        execution.place_taker(
            PlaceOrderRequest("UNKNOWN", TradeSide.BUY, PositionAction.OPEN, 100)
        )