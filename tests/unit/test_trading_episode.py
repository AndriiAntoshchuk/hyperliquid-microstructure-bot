import pytest

from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill

WALLET = "0x1234567890123456789012345678901234567890"

def make_fill(timestamp: float, side: str, quantity: float = 10, price: float = 1.0, start_position: float = 0) -> WalletFill:
    return WalletFill(
        wallet=WALLET,
        coin="PONS",
        timestamp=timestamp,
        price=price,
        quantity=quantity,
        side=side,
        trade_id=f"{timestamp}:PONS:{side}",
        direction="Buy" if side == "buy" else "Sell",
        order_id=int(timestamp),
        closed_pnl=0,
        crossed=False,
        fee=0,
        fee_token="USDC",
        transaction_hash="0xabc",
        start_position=start_position
    )

def test_trading_episode_creation():
    fills = (
        make_fill(1000, "buy", 10, 1.0, 0),
        make_fill(1010, "sell", 10, 1.1, 10)
    )

    episode = TradingEpisode(
        wallet=WALLET,
        coin="PONS",
        start_ts=1000,
        end_ts=1010,
        fills=fills,
        realized_pnl=1
    )

    assert episode.duration == 10
    assert episode.number_of_fills == 2
    assert episode.direction == "long"
    assert episode.max_position_size == 10
    assert episode.vwap_entry == 1.0
    assert episode.vwap_exit == 1.1
    assert episode.return_pct == pytest.approx(10)

def test_short_episode_metrics():
    fills = (
        make_fill(1000, "sell", 10, 1.0, 0),
        make_fill(1010, "buy", 10, 0.9, -10)
    )

    episode = TradingEpisode(
        wallet=WALLET,
        coin="PONS",
        start_ts=1000,
        end_ts=1010,
        fills=fills,
        realized_pnl=1
    )

    assert episode.direction == "short"
    assert episode.max_position_size == 10
    assert episode.vwap_entry == 1.0
    assert episode.vwap_exit == 0.9
    assert episode.return_pct == pytest.approx(11.111111)

def test_episode_rejects_invalid_time_range():
    with pytest.raises(ValueError):
        TradingEpisode(
            wallet=WALLET,
            coin="PONS",
            start_ts=1010,
            end_ts=1000,
            fills=(make_fill(1000, "buy"),),
            realized_pnl=0
        )