from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.fill import ExecutionFill
from hlbot.execution.interface import AdapterOrder, AdapterPosition, PositionAction
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.execution.reconciliation import ExecutionReconciler, ReconciliationIssueType
from hlbot.models.trade import TradeSide

class FakeAdapter:
    def __init__(self, orders=(), positions=None):
        self.orders = tuple(orders)
        self.positions = positions or {}

    def active_orders(self):
        return self.orders

    def position(self, coin):
        return self.positions.get(
            coin,
            AdapterPosition(coin, 0, None, 0, 1)
        )

def local_order(
    client_order_id="cid-1",
    status=OrderStatus.OPEN,
    exchange_order_id="oid-1",
    filled_quantity=0,
    average_fill_price=None
):
    return ExecutionOrderState(
        client_order_id=client_order_id,
        status=status,
        submitted_ts=100,
        updated_ts=101,
        exchange_order_id=exchange_order_id,
        filled_quantity=filled_quantity,
        average_fill_price=average_fill_price
    )

def exchange_order(client_order_id="cid-1", exchange_order_id="oid-1"):
    return AdapterOrder(
        client_order_id,
        exchange_order_id,
        "PONS",
        TradeSide.BUY,
        PositionAction.OPEN,
        "open"
    )

def issue_types(report):
    return {issue.kind for issue in report.issues}

def test_matching_empty_state_is_healthy():
    report = ExecutionReconciler(
        FakeAdapter(),
        OrderTracker(),
        AccountTracker(10000),
        ("PONS",)
    ).reconcile()

    assert report.healthy
    assert report.count == 0

def test_local_active_order_missing_on_exchange():
    orders = OrderTracker()
    orders.add(local_order())

    report = ExecutionReconciler(
        FakeAdapter(),
        orders,
        AccountTracker(10000),
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.LOCAL_ACTIVE_ORDER_MISSING in issue_types(report)

def test_exchange_order_unknown_locally():
    report = ExecutionReconciler(
        FakeAdapter((exchange_order(),)),
        OrderTracker(),
        AccountTracker(10000),
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.EXCHANGE_ORDER_UNKNOWN in issue_types(report)

def test_exchange_order_id_mismatch():
    orders = OrderTracker()
    orders.add(local_order(exchange_order_id="local-oid"))

    report = ExecutionReconciler(
        FakeAdapter((exchange_order(exchange_order_id="exchange-oid"),)),
        orders,
        AccountTracker(10000),
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.EXCHANGE_ORDER_ID_MISMATCH in issue_types(report)

def test_terminal_local_order_active_on_exchange():
    orders = OrderTracker()
    orders.add(local_order(
        status=OrderStatus.FILLED,
        filled_quantity=1,
        average_fill_price=10
    ))

    report = ExecutionReconciler(
        FakeAdapter((exchange_order(),)),
        orders,
        AccountTracker(10000),
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.TERMINAL_ORDER_ACTIVE in issue_types(report)

def test_matching_position_is_healthy():
    account = AccountTracker(10000)
    account.apply_fill(ExecutionFill(
        "fill-1",
        "cid-1",
        "PONS",
        TradeSide.BUY,
        2,
        10,
        0,
        100
    ))

    adapter = FakeAdapter(
        positions={
            "PONS": AdapterPosition("PONS", 2, 10, 0, 5)
        }
    )

    report = ExecutionReconciler(
        adapter,
        OrderTracker(),
        account,
        ("PONS",)
    ).reconcile()

    assert report.healthy

def test_position_quantity_mismatch():
    account = AccountTracker(10000)
    account.apply_fill(ExecutionFill(
        "fill-1",
        "cid-1",
        "PONS",
        TradeSide.BUY,
        2,
        10,
        0,
        100
    ))

    adapter = FakeAdapter(
        positions={
            "PONS": AdapterPosition("PONS", 3, 10, 0, 5)
        }
    )

    report = ExecutionReconciler(
        adapter,
        OrderTracker(),
        account,
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.POSITION_QUANTITY_MISMATCH in issue_types(report)

def test_position_entry_price_mismatch():
    account = AccountTracker(10000)
    account.apply_fill(ExecutionFill(
        "fill-1",
        "cid-1",
        "PONS",
        TradeSide.BUY,
        2,
        10,
        0,
        100
    ))

    adapter = FakeAdapter(
        positions={
            "PONS": AdapterPosition("PONS", 2, 11, 0, 5)
        }
    )

    report = ExecutionReconciler(
        adapter,
        OrderTracker(),
        account,
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.POSITION_ENTRY_PRICE_MISMATCH in issue_types(report)

def test_unconfigured_local_position_is_reported():
    account = AccountTracker(10000)
    account.apply_fill(ExecutionFill(
        "fill-1",
        "cid-1",
        "PURR",
        TradeSide.BUY,
        2,
        10,
        0,
        100
    ))

    report = ExecutionReconciler(
        FakeAdapter(),
        OrderTracker(),
        account,
        ("PONS",)
    ).reconcile()

    assert ReconciliationIssueType.LOCAL_POSITION_UNCONFIGURED in issue_types(report)