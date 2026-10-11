from hlbot.execution.account_tracker import AccountTracker
from hlbot.execution.fill import ExecutionFill
from hlbot.execution.order_state import ExecutionOrderState, OrderStatus
from hlbot.execution.order_tracker import OrderTracker
from hlbot.models.trade import TradeSide
from hlbot.risk.context_builder import RiskContextBuilder

TIMESTAMP = 1_700_000_000

def builder():
    account = AccountTracker(10000)
    orders = OrderTracker()
    return RiskContextBuilder(account, orders), account, orders

def test_builds_empty_account_context():
    context_builder, _, _ = builder()

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001,
        execution_latency_ms=50
    )

    assert context.equity == 10000
    assert context.peak_equity == 10000
    assert context.realized_pnl_today == 0
    assert context.current_position_notional == 0
    assert context.open_orders == 0
    assert context.market_data_age_seconds == .5

def test_position_notional_comes_from_account_tracker():
    context_builder, account, _ = builder()

    account.apply_fill(
        ExecutionFill(
            "fill-1",
            "order-1",
            "TEST",
            TradeSide.BUY,
            2,
            100,
            0,
            TIMESTAMP - 10
        )
    )
    account.update_mark("TEST", 110)

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001
    )

    assert context.current_position_notional == 220
    assert context.equity == 10020

def test_open_orders_come_from_order_tracker():
    context_builder, _, orders = builder()

    orders.add(
        ExecutionOrderState(
            client_order_id="order-1",
            status=OrderStatus.OPEN,
            submitted_ts=TIMESTAMP - 10,
            updated_ts=TIMESTAMP - 5
        )
    )

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001
    )

    assert context.open_orders == 1

def test_terminal_orders_are_not_counted():
    context_builder, _, orders = builder()

    orders.add(
        ExecutionOrderState(
            client_order_id="order-1",
            status=OrderStatus.FILLED,
            submitted_ts=TIMESTAMP - 10,
            updated_ts=TIMESTAMP - 5,
            filled_quantity=1,
            average_fill_price=100
        )
    )

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001
    )

    assert context.open_orders == 0

def test_daily_realized_pnl_comes_from_fills():
    context_builder, account, _ = builder()

    account.apply_fill(
        ExecutionFill(
            "fill-1",
            "order-1",
            "TEST",
            TradeSide.BUY,
            1,
            100,
            1,
            TIMESTAMP - 100
        )
    )
    account.apply_fill(
        ExecutionFill(
            "fill-2",
            "order-2",
            "TEST",
            TradeSide.SELL,
            1,
            110,
            1,
            TIMESTAMP - 50
        )
    )

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001
    )

    assert context.realized_pnl_today == 8

def test_connection_and_latency_are_preserved():
    context_builder, _, _ = builder()

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001,
        connection_healthy=False,
        execution_latency_ms=700
    )

    assert not context.connection_healthy
    assert context.execution_latency_ms == 700

def test_builder_uses_only_requested_coin_position():
    context_builder, account, _ = builder()

    account.apply_fill(
        ExecutionFill(
            "fill-1",
            "order-1",
            "OTHER",
            TradeSide.BUY,
            5,
            100,
            0,
            TIMESTAMP - 10
        )
    )

    context = context_builder.build(
        "TEST",
        TIMESTAMP,
        TIMESTAMP - .5,
        spread_bps=2,
        volatility_10s=.001
    )

    assert context.current_position_notional == 0

def test_reconciliation_health_is_forwarded():
    account = AccountTracker(10000)
    orders = OrderTracker()
    builder = RiskContextBuilder(account, orders)

    context = builder.build(
        coin="PONS",
        timestamp=100,
        market_data_ts=99.5,
        spread_bps=2,
        volatility_10s=.001,
        reconciliation_healthy=False
    )

    assert not context.reconciliation_healthy