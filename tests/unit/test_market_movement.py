import json
import math

import pytest

from hlbot.features.market_movement import (
    latest_realized_volatility,
    realized_volatility
)

def test_realized_volatility():
    prices = (100, 101, 100)

    expected = math.sqrt(
        math.log(101 / 100) ** 2 +
        math.log(100 / 101) ** 2
    )

    assert realized_volatility(prices) == pytest.approx(expected)

def test_realized_volatility_requires_two_prices():
    assert realized_volatility((100,)) is None

def test_latest_realized_volatility(tmp_path):
    path = tmp_path / "universe_2026-09-23.jsonl"

    rows = []
    for ts, price in (
        (9400, 100),
        (9700, 101),
        (9800, 102),
        (9900, 101),
        (10000, 103)
    ):
        rows.append({
            "ts": ts,
            "coin": "PONS",
            "mid_price": price
        })

    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows)
    )

    result = latest_realized_volatility(
        tmp_path,
        ("PONS",),
        now=10000,
        window_seconds=300
    )

    assert result["PONS"] is not None
    assert result["PONS"] > 0