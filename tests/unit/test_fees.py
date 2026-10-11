import pytest

from hlbot.backtest.execution_policy import ExecutionMode
from hlbot.backtest.fees import FeeSchedule

def test_default_fee_schedule_is_zero():
    fees = FeeSchedule()

    assert fees.bps_for(ExecutionMode.TAKER) == 0
    assert fees.bps_for(ExecutionMode.MAKER) == 0

def test_taker_and_maker_fees_are_separate():
    fees = FeeSchedule(taker_bps=4.5, maker_bps=1.5)

    assert fees.fee_for(1000, ExecutionMode.TAKER) == pytest.approx(0.45)
    assert fees.fee_for(1000, ExecutionMode.MAKER) == pytest.approx(0.15)

def test_negative_maker_fee_represents_rebate():
    fees = FeeSchedule(taker_bps=4, maker_bps=-1)

    assert fees.fee_for(1000, ExecutionMode.MAKER) == pytest.approx(-0.1)

def test_negative_taker_fee_is_rejected():
    with pytest.raises(ValueError):
        FeeSchedule(taker_bps=-1)

def test_non_finite_fee_is_rejected():
    with pytest.raises(ValueError):
        FeeSchedule(taker_bps=float("inf"))

    with pytest.raises(ValueError):
        FeeSchedule(maker_bps=float("nan"))

def test_invalid_notional_is_rejected():
    fees = FeeSchedule()

    with pytest.raises(ValueError):
        fees.fee_for(-1, ExecutionMode.TAKER)