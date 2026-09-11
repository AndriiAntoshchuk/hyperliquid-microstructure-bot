import pytest

from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill
from hlbot.wallet_analysis.pnl_analysis import analyze_wallet_performance

WALLET = "0x1234567890123456789012345678901234567890"

def make_episode(start_ts: float, end_ts: float, pnl: float, coin: str = "PONS") -> TradingEpisode:
    fill = WalletFill(
        wallet=WALLET,
        coin=coin,
        timestamp=start_ts,
        price=1.0,
        quantity=1,
        side="buy",
        trade_id=f"{start_ts}:{coin}",
        direction="Open Long",
        order_id=int(start_ts),
        closed_pnl=pnl,
        crossed=False,
        fee=0,
        fee_token="USDC",
        transaction_hash="0xabc",
        start_position=0
    )

    return TradingEpisode(
        wallet=WALLET,
        coin=coin,
        start_ts=start_ts,
        end_ts=end_ts,
        fills=(fill,),
        realized_pnl=pnl
    )

def test_wallet_performance():
    episodes = [
        make_episode(1000, 1100, 10),
        make_episode(1200, 1300, -5),
        make_episode(1400, 1500, 20),
        make_episode(1600, 1700, -2)
    ]

    report = analyze_wallet_performance(episodes)

    assert report.total_pnl == 23
    assert report.number_of_episodes == 4
    assert report.win_rate == 0.5
    assert report.average_pnl == pytest.approx(5.75)
    assert report.median_pnl == pytest.approx(4)
    assert report.best_pnl == 20
    assert report.worst_pnl == -5
    assert report.max_drawdown == 5
    assert report.longest_losing_streak == 1
    assert report.top_1_pct_contribution == pytest.approx(20 / 23)
    assert report.top_5_pct_contribution == pytest.approx(20 / 23)
    assert report.pnl_without_top_1_pct == 3
    assert report.pnl_without_top_5_pct == 3

def test_empty_wallet_performance():
    report = analyze_wallet_performance([])

    assert report.total_pnl == 0
    assert report.number_of_episodes == 0
    assert report.win_rate == 0
    assert report.max_drawdown == 0