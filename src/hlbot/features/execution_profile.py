from dataclasses import asdict

from hlbot.features.execution_capacity import analyze_execution_capacity

def build_execution_profile(
    markets,
    ready,
    data_dir,
    now,
    notionals=(100, 250, 500, 750, 1000, 1500, 2000),
    window_seconds=3600,
    minimum_full_rate=0.95
):
    rows = []

    for market in sorted(markets, key=lambda row: row["rank"]):
        coin = market["coin"]
        supported = market["dex"] == "main"
        l2_ready = ready.get(coin, False)

        row = {
            "dex": market["dex"],
            "coin": coin,
            "rank": market["rank"],
            "execution_supported": supported,
            "l2_ready": l2_ready,
            "max_notional": None,
            "curve": []
        }

        if supported and l2_ready:
            capacity = analyze_execution_capacity(
                data_dir,
                coin,
                now,
                notionals,
                window_seconds,
                minimum_full_rate
            )
            row["max_notional"] = capacity.max_notional
            row["curve"] = [
                {
                    "notional": notional,
                    "quality": asdict(quality)
                }
                for notional, quality in capacity.curve
            ]

        rows.append(row)

    return tuple(rows)