import pytest

from hlbot.models.wallet_fill import WalletFill

def make_fill(side: str = "buy") -> WalletFill:
    return WalletFill(
        wallet="0x1234567890123456789012345678901234567890",
        coin="PONS",
        timestamp=1000,
        price=0.8,
        quantity=100,
        side=side,
        trade_id="1000000:PONS:123",
        direction="Open Long",
        order_id=123,
        closed_pnl=0,
        crossed=False,
        fee=0.01,
        fee_token="USDC",
        transaction_hash="0xabc"
    )

def test_wallet_fill_creation():
    fill = make_fill()

    assert fill.coin == "PONS"
    assert fill.side == "buy"

def test_wallet_fill_rejects_invalid_side():
    with pytest.raises(ValueError):
        make_fill("invalid")