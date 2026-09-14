import pytest

from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill
from hlbot.wallet_analysis.position_sizing import analyze_episode_sizing, build_order_executions, end_position, position_change_type, summarize_position_sizing

def make_fill(timestamp: float, price: float, quantity: float, side: str, start_position: float, order_id: int) -> WalletFill:
    return WalletFill(
        wallet="0xwallet",
        coin="PONS",
        timestamp=timestamp,
        price=price,
        quantity=quantity,
        side=side,
        trade_id=f"{timestamp}:{order_id}",
        direction="Open Long" if side == "buy" else "Close Long",
        order_id=order_id,
        closed_pnl=0,
        crossed=True,
        fee=0,
        fee_token="USDC",
        transaction_hash="0xhash",
        start_position=start_position
    )

def make_episode() -> TradingEpisode:
    fills = (
        make_fill(1, 100, 0.4, "buy", 0, 10),
        make_fill(2, 101, 0.6, "buy", 0.4, 10),
        make_fill(3, 102, 0.5, "buy", 1, 11),
        make_fill(4, 103, 0.5, "buy", 1.5, 11),
        make_fill(5, 104, 0.5, "sell", 2, 12),
        make_fill(6, 105, 1.5, "sell", 1.5, 12)
    )

    return TradingEpisode(
        wallet="0xwallet",
        coin="PONS",
        start_ts=1,
        end_ts=6,
        fills=fills,
        realized_pnl=5
    )

def test_end_position():
    fill = make_fill(1, 100, 2, "buy", 3, 1)

    assert end_position(fill) == 5

def test_position_change_types():
    entry = make_fill(1, 100, 1, "buy", 0, 1)
    scale_in = make_fill(2, 100, 1, "buy", 1, 2)
    scale_out = make_fill(3, 100, 0.5, "sell", 2, 3)
    flip = make_fill(4, 100, 2, "sell", 1, 4)

    assert position_change_type(entry) == "entry"
    assert position_change_type(scale_in) == "scale_in"
    assert position_change_type(scale_out) == "scale_out"
    assert position_change_type(flip) == "flip"

def test_multiple_fills_are_grouped_into_orders():
    orders = build_order_executions(make_episode())

    assert len(orders) == 3
    assert orders[0].order_id == 10
    assert orders[0].fill_count == 2
    assert orders[0].quantity == pytest.approx(1)
    assert orders[0].notional == pytest.approx(100.6)
    assert orders[0].change_type == "entry"

    assert orders[1].fill_count == 2
    assert orders[1].notional == pytest.approx(102.5)
    assert orders[1].change_type == "scale_in"

    assert orders[2].fill_count == 2
    assert orders[2].change_type == "scale_out"

def test_analyze_episode_sizing_uses_orders():
    result = analyze_episode_sizing(make_episode())

    assert result.number_of_orders == 3
    assert result.initial_entry_fill_count == 2
    assert result.initial_entry_notional == pytest.approx(100.6)
    assert result.max_position_notional == pytest.approx(208)
    assert result.total_entry_notional == pytest.approx(203.1)
    assert result.scale_in_count == 1
    assert result.scale_out_count == 1
    assert result.flip_count == 0
    assert result.scale_ratio == pytest.approx(208 / 100.6)
    assert result.scaled_in

def test_summary():
    observation = analyze_episode_sizing(make_episode())
    summary = summarize_position_sizing([observation])

    assert summary.episodes == 1
    assert summary.average_initial_entry_notional == pytest.approx(100.6)
    assert summary.median_max_position_notional == pytest.approx(208)
    assert summary.average_orders_per_episode == 3
    assert summary.average_scale_in_count == 1
    assert summary.scaled_in_fraction == 1