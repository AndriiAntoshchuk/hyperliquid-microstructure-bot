import pytest

from hlbot.models.wallet_fill import WalletFill


def test_wallet_fill_creation():
    fill = WalletFill(
        wallet="0x123",
        coin="PONS",
        timestamp=1000,
        price=0.8,
        quantity=100,
        side="buy",
        trade_id="1000:PONS:123",
    )

    assert fill.coin == "PONS"
    assert fill.side == "buy"


def test_wallet_fill_rejects_invalid_side():
    with pytest.raises(ValueError):
        WalletFill(
            wallet="0x123",
            coin="PONS",
            timestamp=1000,
            price=0.8,
            quantity=100,
            side="invalid",
            trade_id="123",
        )