from hlbot.models.wallet_fill import WalletFill
from hlbot.wallet_analysis.episode_builder import EpisodeBuilder

WALLET = "0x1234567890123456789012345678901234567890"

def make_fill(timestamp: float, side: str, quantity: float, start_position: float, direction: str, closed_pnl: float = 0) -> WalletFill:
    return WalletFill(
        wallet=WALLET,
        coin="PONS",
        timestamp=timestamp,
        price=1.0,
        quantity=quantity,
        side=side,
        trade_id=f"{timestamp}:PONS:{side}:{quantity}:{start_position}",
        direction=direction,
        order_id=int(timestamp),
        closed_pnl=closed_pnl,
        crossed=False,
        fee=0,
        fee_token="USDC",
        transaction_hash="0xabc",
        start_position=start_position
    )

def test_long_episode():
    fills = [
        make_fill(1, "buy", 10, 0, "Open Long"),
        make_fill(2, "sell", 10, 10, "Close Long", 5)
    ]

    episodes = EpisodeBuilder().build(fills)

    assert len(episodes) == 1
    assert episodes[0].number_of_fills == 2
    assert episodes[0].realized_pnl == 5

def test_short_episode():
    fills = [
        make_fill(1, "sell", 10, 0, "Open Short"),
        make_fill(2, "buy", 10, -10, "Close Short", 4)
    ]

    episodes = EpisodeBuilder().build(fills)

    assert len(episodes) == 1
    assert episodes[0].realized_pnl == 4

def test_scaling_and_partial_exits():
    fills = [
        make_fill(1, "buy", 10, 0, "Open Long"),
        make_fill(2, "buy", 5, 10, "Open Long"),
        make_fill(3, "sell", 8, 15, "Close Long", 2),
        make_fill(4, "sell", 7, 7, "Close Long", 3)
    ]

    episodes = EpisodeBuilder().build(fills)

    assert len(episodes) == 1
    assert episodes[0].number_of_fills == 4
    assert episodes[0].realized_pnl == 5

def test_initial_incomplete_position_is_skipped():
    fills = [
        make_fill(1, "sell", 5, 10, "Close Long"),
        make_fill(2, "sell", 5, 5, "Close Long"),
        make_fill(3, "buy", 3, 0, "Open Long"),
        make_fill(4, "sell", 3, 3, "Close Long", 2)
    ]

    episodes = EpisodeBuilder().build(fills)

    assert len(episodes) == 1
    assert episodes[0].start_ts == 3
    assert episodes[0].realized_pnl == 2

def test_open_episode_at_end_is_ignored():
    fills = [make_fill(1, "buy", 5, 0, "Open Long")]

    assert EpisodeBuilder().build(fills) == []

def test_position_flip():
    fills = [
        make_fill(1, "buy", 5, 0, "Open Long"),
        make_fill(2, "sell", 8, 5, "Close Long", 3),
        make_fill(3, "buy", 3, -3, "Close Short", 2)
    ]

    episodes = EpisodeBuilder().build(fills)

    assert len(episodes) == 2
    assert episodes[0].realized_pnl == 3
    assert episodes[1].realized_pnl == 2