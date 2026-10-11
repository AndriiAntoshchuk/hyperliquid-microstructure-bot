from dataclasses import dataclass
from enum import Enum
from math import isclose, isfinite

from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.interface import ExecutionAdapter
from hlbot.execution.order_tracker import OrderTracker

class ReconciliationIssueType(Enum):
    LOCAL_ACTIVE_ORDER_MISSING = "local_active_order_missing"
    EXCHANGE_ORDER_UNKNOWN = "exchange_order_unknown"
    EXCHANGE_ORDER_ID_MISMATCH = "exchange_order_id_mismatch"
    TERMINAL_ORDER_ACTIVE = "terminal_order_active"
    POSITION_QUANTITY_MISMATCH = "position_quantity_mismatch"
    POSITION_ENTRY_PRICE_MISMATCH = "position_entry_price_mismatch"
    LOCAL_POSITION_UNCONFIGURED = "local_position_unconfigured"

@dataclass(frozen=True)
class ReconciliationIssue:
    kind: ReconciliationIssueType
    key: str
    message: str

@dataclass(frozen=True)
class ReconciliationReport:
    issues: tuple[ReconciliationIssue, ...]

    @property
    def healthy(self) -> bool:
        return not self.issues

    @property
    def count(self) -> int:
        return len(self.issues)

class ExecutionReconciler:
    def __init__(
        self,
        adapter: ExecutionAdapter,
        orders: OrderTracker,
        account: AccountTracker,
        coins,
        quantity_tolerance: float = 1e-9,
        price_tolerance: float = 1e-9
    ):
        coins = tuple(coins)
        if not coins: raise ValueError("coins cannot be empty")
        if len(set(coins)) != len(coins): raise ValueError("coins cannot contain duplicates")
        if any(not coin for coin in coins): raise ValueError("coin cannot be empty")
        if not isfinite(quantity_tolerance) or quantity_tolerance < 0:
            raise ValueError("quantity_tolerance must be non-negative and finite")
        if not isfinite(price_tolerance) or price_tolerance < 0:
            raise ValueError("price_tolerance must be non-negative and finite")

        self.adapter = adapter
        self.orders = orders
        self.account = account
        self.coins = coins
        self.quantity_tolerance = quantity_tolerance
        self.price_tolerance = price_tolerance

    def reconcile(self) -> ReconciliationReport:
        issues = []
        issues.extend(self._order_issues())
        issues.extend(self._position_issues())
        return ReconciliationReport(tuple(issues))

    def _order_issues(self) -> list[ReconciliationIssue]:
        issues = []
        local = {order.client_order_id: order for order in self.orders.all_orders()}
        exchange = {order.client_order_id: order for order in self.adapter.active_orders()}

        for client_order_id, order in local.items():
            if order.active and client_order_id not in exchange:
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.LOCAL_ACTIVE_ORDER_MISSING,
                    client_order_id,
                    "local active order is missing from exchange active orders"
                ))

        for client_order_id, exchange_order in exchange.items():
            local_order = local.get(client_order_id)

            if local_order is None:
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.EXCHANGE_ORDER_UNKNOWN,
                    client_order_id,
                    "exchange active order is unknown locally"
                ))
                continue

            if local_order.terminal:
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.TERMINAL_ORDER_ACTIVE,
                    client_order_id,
                    f"local {local_order.status.value} order is active on exchange"
                ))
                continue

            if (
                local_order.exchange_order_id is not None
                and exchange_order.exchange_order_id is not None
                and local_order.exchange_order_id != exchange_order.exchange_order_id
            ):
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.EXCHANGE_ORDER_ID_MISMATCH,
                    client_order_id,
                    f"local exchange id {local_order.exchange_order_id} != exchange {exchange_order.exchange_order_id}"
                ))

        return issues

    def _position_issues(self) -> list[ReconciliationIssue]:
        issues = []
        configured = set(self.coins)

        for position in self.account.positions():
            if position.quantity != 0 and position.coin not in configured:
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.LOCAL_POSITION_UNCONFIGURED,
                    position.coin,
                    "local open position is not configured for reconciliation"
                ))

        for coin in self.coins:
            local = self.account.position(coin)
            exchange = self.adapter.position(coin)

            if not isclose(
                local.quantity,
                exchange.quantity,
                rel_tol=0,
                abs_tol=self.quantity_tolerance
            ):
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.POSITION_QUANTITY_MISMATCH,
                    coin,
                    f"local quantity {local.quantity} != exchange {exchange.quantity}"
                ))

            if local.quantity == 0 or exchange.quantity == 0:
                continue

            local_price = local.average_entry_price
            exchange_price = exchange.entry_price

            if local_price is None or exchange_price is None:
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.POSITION_ENTRY_PRICE_MISMATCH,
                    coin,
                    f"local entry {local_price} != exchange {exchange_price}"
                ))
                continue

            if not isclose(
                local_price,
                exchange_price,
                rel_tol=self.price_tolerance,
                abs_tol=self.price_tolerance
            ):
                issues.append(ReconciliationIssue(
                    ReconciliationIssueType.POSITION_ENTRY_PRICE_MISMATCH,
                    coin,
                    f"local entry {local_price} != exchange {exchange_price}"
                ))

        return issues