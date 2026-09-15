import pytest

from hlbot.strategy.specification import StrategySpec, next_order_notional, remaining_position_capacity, scale_order_notional

def make_spec() -> StrategySpec:
    return StrategySpec(
        base_order_notional=1000,
        max_position_notional=6000,
        max_scale_ins=5
    )

def test_equal_sized_orders_by_default():
    spec = make_spec()

    assert scale_order_notional(spec, 0) == 1000
    assert scale_order_notional(spec, 1) == 1000
    assert scale_order_notional(spec, 5) == 1000

def test_number_of_entry_orders():
    spec = make_spec()

    assert spec.max_entry_orders == 6

def test_position_capacity():
    spec = make_spec()

    assert remaining_position_capacity(spec, 0) == 6000
    assert remaining_position_capacity(spec, 2000) == 4000
    assert remaining_position_capacity(spec, 6000) == 0
    assert remaining_position_capacity(spec, 7000) == 0

def test_next_order_respects_position_cap():
    spec = make_spec()

    assert next_order_notional(spec, 0, 0) == 1000
    assert next_order_notional(spec, 5000, 5) == 1000
    assert next_order_notional(spec, 5500, 5) == 500
    assert next_order_notional(spec, 6000, 5) == 0

def test_scale_in_limit():
    spec = make_spec()

    assert next_order_notional(spec, 0, 5) == 1000
    assert next_order_notional(spec, 0, 6) == 0

def test_non_unit_scale_multiplier():
    spec = StrategySpec(
        base_order_notional=1000,
        max_position_notional=10000,
        max_scale_ins=3,
        scale_order_multiplier=1.5
    )

    assert scale_order_notional(spec, 0) == 1000
    assert scale_order_notional(spec, 1) == 1500
    assert scale_order_notional(spec, 2) == 2250

def test_invalid_specification():
    with pytest.raises(ValueError):
        StrategySpec(
            base_order_notional=1000,
            max_position_notional=500,
            max_scale_ins=1
        )

    with pytest.raises(ValueError):
        StrategySpec(
            base_order_notional=1000,
            max_position_notional=5000,
            max_scale_ins=-1
        )

    with pytest.raises(ValueError):
        StrategySpec(
            base_order_notional=1000,
            max_position_notional=5000,
            max_scale_ins=2,
            stop_loss_pct=0
        )