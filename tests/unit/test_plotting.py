import pytest

from hlbot.backtest.capital import CapitalPoint
from hlbot.backtest.plotting import drawdown_curve, timestamps_to_utc

def test_timestamps_to_utc():
    times = timestamps_to_utc([1000, 2000])

    assert len(times) == 2
    assert times[0].timestamp() == pytest.approx(1000)
    assert times[1].timestamp() == pytest.approx(2000)

def test_drawdown_curve():
    curve = (
		CapitalPoint(1, 1000, 0, 1000),
		CapitalPoint(2, 1010, 0, 1010),
		CapitalPoint(3, 1000, 0, 1000),
		CapitalPoint(4, 1020, 0, 1020),
		CapitalPoint(5, 1005, 0, 1005)
    )

    drawdowns = drawdown_curve(curve)

    assert drawdowns[0] == pytest.approx(0)
    assert drawdowns[1] == pytest.approx(0)
    assert drawdowns[2] == pytest.approx(10 / 1010 * 100)
    assert drawdowns[3] == pytest.approx(0)
    assert drawdowns[4] == pytest.approx(15 / 1020 * 100)

def test_empty_drawdown_curve():
    assert drawdown_curve(()) == ()