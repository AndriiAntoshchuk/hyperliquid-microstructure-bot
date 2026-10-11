import pytest

from hlbot.backtest.capital import build_capital_curve, max_drawdown_pct, return_pct
from hlbot.backtest.replay import ReplayEquityPoint

def make_curve():
    return (
        ReplayEquityPoint(1, 0, 0, 0, 0),
        ReplayEquityPoint(2, 10, 5, 1, 14),
        ReplayEquityPoint(3, 10, -5, 1, 4),
        ReplayEquityPoint(4, 20, 0, 2, 18)
    )

def test_capital_curve_adds_initial_balance():
    curve = build_capital_curve(make_curve(), 1000)

    assert curve[0].balance == pytest.approx(1000)
    assert curve[0].equity == pytest.approx(1000)

    assert curve[1].balance == pytest.approx(1009)
    assert curve[1].equity == pytest.approx(1014)
    assert curve[1].unrealized_pnl == pytest.approx(5)

def test_balance_excludes_unrealized_pnl():
    curve = build_capital_curve(make_curve(), 1000)

    assert curve[2].balance == pytest.approx(1009)
    assert curve[2].equity == pytest.approx(1004)

def test_return_pct():
    assert return_pct(1000, 1100) == pytest.approx(10)
    assert return_pct(1000, 900) == pytest.approx(-10)

def test_max_drawdown_pct():
    curve = build_capital_curve(make_curve(), 1000)

    expected = (1014 - 1004) / 1014 * 100

    assert max_drawdown_pct(curve) == pytest.approx(expected)

def test_invalid_initial_balance_is_rejected():
    with pytest.raises(ValueError):
        build_capital_curve(make_curve(), 0)

    with pytest.raises(ValueError):
        return_pct(-1, 1000)