import pytest

from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill
from hlbot.research.event_study import EventStudyPoint
from hlbot.research.momentum_mean_reversion import analyze_episode, classify_entry_style, price_return_pct, signed_return, summarize_observations

def make_fill(side: str = "buy") -> WalletFill:
    return WalletFill(
        wallet="0xwallet",
        coin="PONS",
        timestamp=100,
        price=100,
        quantity=1,
        side=side,
        trade_id="1",
        direction="Open Long" if side == "buy" else "Open Short",
        order_id=1,
        closed_pnl=0,
        crossed=True,
        fee=0,
        fee_token="USDC",
        transaction_hash="0xhash",
        start_position=0
    )

def make_episode(side: str = "buy") -> TradingEpisode:
    fill = make_fill(side)

    return TradingEpisode(
        wallet="0xwallet",
        coin="PONS",
        start_ts=100,
        end_ts=110,
        fills=(fill,),
        realized_pnl=1
    )

def make_point(offset: int, price: float) -> EventStudyPoint:
    return EventStudyPoint(
        event_ts=100,
        offset_seconds=offset,
        target_ts=100 + offset,
        market_ts=100 + offset,
        mid_price=price,
        spread_bps=1,
        imbalance_1=0,
        imbalance_5=0,
        weighted_imbalance_5=0,
        microprice=price,
        trade_flow_5s=0,
        volatility_10s=0,
        bid_liquidity_10bps=100,
        ask_liquidity_10bps=100
    )

def test_price_return():
    assert price_return_pct(100, 101) == pytest.approx(1)

def test_signed_return():
    assert signed_return(2, "long") == 2
    assert signed_return(2, "short") == -2

def test_classify_entry_style():
    assert classify_entry_style(1) == "momentum"
    assert classify_entry_style(-1) == "mean_reversion"
    assert classify_entry_style(0) == "neutral"

def test_long_momentum_entry():
    episode = make_episode("buy")
    points = [
        make_point(-10, 99),
        make_point(0, 100),
        make_point(10, 101)
    ]

    result = analyze_episode(episode, points)

    assert result is not None
    assert result.direction == "long"
    assert result.entry_style == "momentum"
    assert result.signed_pre_return_pct > 0
    assert result.signed_post_return_pct > 0

def test_long_mean_reversion_entry():
    episode = make_episode("buy")
    points = [
        make_point(-10, 101),
        make_point(0, 100),
        make_point(10, 102)
    ]

    result = analyze_episode(episode, points)

    assert result is not None
    assert result.entry_style == "mean_reversion"
    assert result.signed_pre_return_pct < 0
    assert result.signed_post_return_pct > 0

def test_short_momentum_entry():
    episode = make_episode("sell")
    points = [
        make_point(-10, 101),
        make_point(0, 100),
        make_point(10, 99)
    ]

    result = analyze_episode(episode, points)

    assert result is not None
    assert result.direction == "short"
    assert result.entry_style == "momentum"
    assert result.signed_pre_return_pct > 0
    assert result.signed_post_return_pct > 0

def test_missing_offset_is_rejected():
    episode = make_episode()
    points = [
        make_point(-10, 99),
        make_point(0, 100)
    ]

    assert analyze_episode(episode, points) is None

def test_summary():
    observations = [
        analyze_episode(
            make_episode("buy"),
            [make_point(-10, 99), make_point(0, 100), make_point(10, 101)]
        ),
        analyze_episode(
            make_episode("buy"),
            [make_point(-10, 101), make_point(0, 100), make_point(10, 102)]
        )
    ]

    observations = [item for item in observations if item is not None]
    summary = summarize_observations(observations)

    assert summary.observations == 2
    assert summary.momentum_entries == 1
    assert summary.mean_reversion_entries == 1
    assert summary.momentum_fraction == 0.5
    assert summary.mean_reversion_fraction == 0.5