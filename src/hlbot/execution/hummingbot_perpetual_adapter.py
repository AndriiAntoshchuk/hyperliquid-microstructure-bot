from decimal import Decimal

from hlbot.execution.interface import AdapterBalance, AdapterOrder, AdapterPosition, PlaceOrderRequest, PositionAction
from hlbot.execution.perpetual_config import MarginMode, PerpetualExecutionConfig
from hlbot.models.trade import TradeSide

class HummingbotPerpetualAdapter:
    def __init__(self, connector, trading_pairs, config, market_type, maker_type, hb_open, hb_close, hb_oneway):
        self.connector = connector
        self.trading_pairs = trading_pairs
        self.config = config
        self.market_type = market_type
        self.maker_type = maker_type
        self.hb_open = hb_open
        self.hb_close = hb_close
        self.hb_oneway = hb_oneway
        self._order_pairs = {}

    @classmethod
    def from_connector(cls, connector, trading_pairs: dict[str, str], config: PerpetualExecutionConfig):
        from hummingbot.core.data_type.common import OrderType, PositionAction as HBPositionAction, PositionMode
        return cls(
            connector, trading_pairs, config,
            OrderType.MARKET, OrderType.LIMIT_MAKER,
            HBPositionAction.OPEN, HBPositionAction.CLOSE,
            PositionMode.ONEWAY
        )

    def request_configuration(self) -> None:
        for market in self.config.markets:
            if market.margin_mode != MarginMode.AUTO:
                raise NotImplementedError("explicit margin mode is not supported by Hummingbot adapter")

        self.connector.set_position_mode(self.hb_oneway)

        for market in self.config.markets:
            self.connector.set_leverage(self._pair(market.coin), market.leverage)

    def configuration_ready(self) -> bool:
        if self.connector.position_mode != self.hb_oneway: return False

        for market in self.config.markets:
            if self.connector.get_leverage(self._pair(market.coin)) != market.leverage:
                return False

        return True

    def place_taker(self, request: PlaceOrderRequest) -> str:
        pair, amount = self._amount(request)
        return self._submit(request, pair, amount, self.market_type, Decimal("NaN"))

    def place_maker(self, request: PlaceOrderRequest) -> str:
        if not request.post_only: raise ValueError("maker request must be post_only")
        pair, amount = self._amount(request)
        price = self.connector.quantize_order_price(pair, Decimal(str(request.price)))
        return self._submit(request, pair, amount, self.maker_type, price)

    def cancel(self, client_order_id: str) -> None:
        pair = self._order_pairs.get(client_order_id)
        if pair is None: raise KeyError(f"unknown order: {client_order_id}")
        self.connector.cancel(pair, client_order_id)

    def replace(self, client_order_id: str, request: PlaceOrderRequest) -> str:
        raise NotImplementedError("safe replacement requires cancellation confirmation")

    def position(self, coin: str) -> AdapterPosition:
        pair = self._pair(coin)

        for position in self.connector.account_positions.values():
            if position.trading_pair != pair: continue
            return AdapterPosition(
                coin,
                float(position.amount),
                float(position.entry_price),
                float(position.unrealized_pnl),
                float(position.leverage)
            )

        return AdapterPosition(coin, 0, None, 0, float(self.connector.get_leverage(pair)))

    def balances(self) -> tuple[AdapterBalance, ...]:
        return tuple(
            AdapterBalance(asset, float(total), float(self.connector.get_available_balance(asset)))
            for asset, total in sorted(self.connector.get_all_balances().items())
        )

    def active_orders(self) -> tuple[AdapterOrder, ...]:
        reverse = {pair: coin for coin, pair in self.trading_pairs.items()}
        orders = []

        for order in self.connector.in_flight_orders.values():
            action = PositionAction.CLOSE if order.position.name == "CLOSE" else PositionAction.OPEN
            orders.append(AdapterOrder(
                order.client_order_id,
                order.exchange_order_id,
                reverse.get(order.trading_pair, order.trading_pair),
                TradeSide.BUY if order.trade_type.name == "BUY" else TradeSide.SELL,
                action,
                order.current_state.name.lower()
            ))

        return tuple(orders)

    def _amount(self, request):
        pair = self._pair(request.coin)
        price = Decimal(str(request.price)) if request.price is not None else Decimal(str(
            self.connector.get_price(pair, request.side == TradeSide.BUY)
        ))
        amount = self.connector.quantize_order_amount(pair, Decimal(str(request.notional)) / price)
        if amount <= 0: raise ValueError("order amount quantized to zero")
        return pair, amount

    def _submit(self, request, pair, amount, order_type, price):
        action = self.hb_close if request.action == PositionAction.CLOSE else self.hb_open
        method = self.connector.buy if request.side == TradeSide.BUY else self.connector.sell
        order_id = method(pair, amount, order_type, price, position_action=action)
        self._order_pairs[order_id] = pair
        return order_id

    def _pair(self, coin):
        try:
            return self.trading_pairs[coin]
        except KeyError:
            raise KeyError(f"unknown coin: {coin}") from None