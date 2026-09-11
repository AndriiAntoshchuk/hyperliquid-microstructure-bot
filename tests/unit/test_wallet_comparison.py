from hlbot.models.trading_episode import TradingEpisode
from hlbot.models.wallet_fill import WalletFill
from hlbot.wallet_analysis.wallet_comparison import compare_wallets, summarize_wallet

def make_episode(wallet: str, coin: str, start_ts: float, end_ts: float, pnl: float, side: str = "buy", price: float = 1.0, quantity: float = 10) -> TradingEpisode:
    fill = WalletFill(
        wallet=wallet,
        coin=coin,
        timestamp=start_ts,
        price=price,
        quantity=quantity,
        side=side,
        trade_id=f"{wallet}:{coin}:{start_ts}",
        direction="Open Long" if side == "buy" else "Open Short",
        order_id=int(start_ts),
        closed_pnl=pnl,
        crossed=False,
        fee=0,
        fee_token="USDC",
        transaction_hash="0xabc",
        start_position=0
    )

    return TradingEpisode(
        wallet=wallet,
        coin=coin,
        start_ts=start_ts,
        end_ts=end_ts,
        fills=(fill,),
        realized_pnl=pnl
    )

def test_summarize_wallet():
    wallet = "0x111"
    episodes = [
        make_episode(wallet, "PONS", 3600, 3610, 10, price=2, quantity=10),
        make_episode(wallet, "ANSEM", 7200, 7230, -5, "sell", price=1, quantity=20)
    ]

    summary = summarize_wallet(wallet, episodes)

    assert summary.number_of_episodes == 2
    assert summary.total_pnl == 5
    assert summary.win_rate == 0.5
    assert summary.average_duration == 20
    assert summary.median_duration == 20
    assert summary.average_fills_per_episode == 1
    assert summary.median_fills_per_episode == 1
    assert summary.average_max_position_notional == 20
    assert summary.long_episodes == 1
    assert summary.short_episodes == 1
    assert summary.coins == ("ANSEM", "PONS")
    assert summary.active_hours_utc == (1, 2)

def test_compare_wallets():
    wallet_a = "0x111"
    wallet_b = "0x222"

    comparison = compare_wallets({
        wallet_a: [
            make_episode(wallet_a, "PONS", 3600, 3610, 10),
            make_episode(wallet_a, "ANSEM", 7200, 7210, 5)
        ],
        wallet_b: [
            make_episode(wallet_b, "PONS", 3600, 3610, 7),
            make_episode(wallet_b, "PURR", 10800, 10810, 3)
        ]
    })

    assert len(comparison.wallets) == 2
    assert len(comparison.pairwise) == 1
    assert comparison.pairwise[0].common_coins == ("PONS",)
    assert comparison.pairwise[0].common_active_hours_utc == (1,)