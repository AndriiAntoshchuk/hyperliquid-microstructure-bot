from hlbot.data.wallet_loader import HyperliquidWalletLoader

WALLET = "0x1234567890123456789012345678901234567890"

def make_raw_fill() -> dict:
    return {
        "coin": "PONS",
        "px": "0.8",
        "sz": "100",
        "side": "B",
        "time": 1000000,
        "startPosition": "25048.08633993",
        "dir": "Open Long",
        "closedPnl": "0",
        "hash": "0xabc",
        "oid": 123,
        "crossed": False,
        "fee": "0.01",
        "tid": 456,
        "cloid": "0xe99f333408ec9565db1de7181bccbba7",
        "feeToken": "USDC",
        "twapId": 42
    }

def test_normalize_fill():
    fill = HyperliquidWalletLoader._normalize_fill(WALLET, make_raw_fill())

    assert fill.coin == "PONS"
    assert fill.price == 0.8
    assert fill.quantity == 100
    assert fill.side == "buy"
    assert fill.trade_id == "1000000:PONS:456"
    assert fill.direction == "Open Long"
    assert fill.order_id == 123
    assert fill.closed_pnl == 0
    assert fill.crossed is False
    assert fill.fee == 0.01
    assert fill.fee_token == "USDC"
    assert fill.transaction_hash == "0xabc"
    assert fill.start_position == 25048.08633993
    assert fill.client_order_id == "0xe99f333408ec9565db1de7181bccbba7"
    assert fill.twap_id == 42

def test_deduplicate():
    fill = HyperliquidWalletLoader._normalize_fill(WALLET, make_raw_fill())
    result = HyperliquidWalletLoader._deduplicate([fill, fill])

    assert len(result) == 1
    assert result[0].trade_id == fill.trade_id