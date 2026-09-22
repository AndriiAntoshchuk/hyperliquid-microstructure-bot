import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

INFO_URL = "https://api.hyperliquid.xyz/info"

@dataclass(frozen=True)
class UniverseMarket:
    ts: float
    dex: str
    coin: str
    is_delisted: bool
    sz_decimals: int
    max_leverage: int
    day_notional_volume: float
    day_base_volume: float
    open_interest: float
    funding: float
    premium: float | None
    oracle_price: float | None
    mark_price: float | None
    mid_price: float | None
    prev_day_price: float | None

    @property
    def active(self) -> bool:
        return not self.is_delisted and self.mid_price is not None
    
    @property
    def open_interest_notional(self) -> float | None:
        return None if self.mark_price is None else self.open_interest * self.mark_price

def post_info(payload: dict, timeout: float = 10) -> Any:
    request = Request(
        INFO_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)

def fetch_dex_names(post: Callable[[dict], Any] = post_info) -> tuple[str, ...]:
    return tuple("" if dex is None else dex["name"] for dex in post({"type": "perpDexs"}))

def parse_asset_contexts(ts: float, dex: str, meta: dict, ctxs: list[dict]) -> tuple[UniverseMarket, ...]:
    universe = meta["universe"]
    if len(universe) != len(ctxs): raise ValueError(f"{dex or 'main'} universe/context length mismatch")

    return tuple(
        UniverseMarket(
            ts=ts,
            dex=dex or "main",
            coin=asset["name"],
            is_delisted=bool(asset.get("isDelisted", False)),
            sz_decimals=int(asset["szDecimals"]),
            max_leverage=int(asset["maxLeverage"]),
            day_notional_volume=float(ctx["dayNtlVlm"]),
            day_base_volume=float(ctx["dayBaseVlm"]),
            open_interest=float(ctx["openInterest"]),
            funding=float(ctx["funding"]),
            premium=_float(ctx.get("premium")),
            oracle_price=_float(ctx.get("oraclePx")),
            mark_price=_float(ctx.get("markPx")),
            mid_price=_float(ctx.get("midPx")),
            prev_day_price=_float(ctx.get("prevDayPx"))
        )
        for asset, ctx in zip(universe, ctxs)
    )

def fetch_universe_snapshot(
    post: Callable[[dict], Any] = post_info,
    dex_names: tuple[str, ...] | None = None,
    timestamp: float | None = None
) -> tuple[UniverseMarket, ...]:
    ts = time.time() if timestamp is None else timestamp
    dex_names = fetch_dex_names(post) if dex_names is None else dex_names
    rows = []

    for dex in dex_names:
        meta, ctxs = post({"type": "metaAndAssetCtxs", "dex": "" if dex == "main" else dex})
        rows.extend(parse_asset_contexts(ts, dex, meta, ctxs))

    return tuple(rows)

class UniverseCollector:
    def __init__(
        self,
        output_dir: str | Path = "data/raw/hyperliquid_universe",
        interval: float = 60,
        post: Callable[[dict], Any] = post_info
    ):
        if interval <= 0: raise ValueError("interval must be positive")
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.post = post
        self.dex_names: tuple[str, ...] | None = None

    def collect_once(self) -> tuple[UniverseMarket, ...]:
        if self.dex_names is None: self.dex_names = fetch_dex_names(self.post)
        rows = fetch_universe_snapshot(self.post, self.dex_names)
        self._write(rows)
        return rows

    def run(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        while True:
            started = time.monotonic()
            try:
                rows = self.collect_once()
                active = sum(row.active for row in rows)
                print(f"{datetime.now().isoformat(timespec='seconds')} markets={len(rows)} active={active}")
            except Exception as exc:
                print(f"{datetime.now().isoformat(timespec='seconds')} collector error: {exc}")

            time.sleep(max(0, self.interval - (time.monotonic() - started)))

    def _write(self, rows: tuple[UniverseMarket, ...]) -> None:
        if not rows: raise ValueError("cannot write empty universe snapshot")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.fromtimestamp(rows[0].ts, timezone.utc).date().isoformat()
        path = self.output_dir / f"universe_{day}.jsonl"
        payload = "".join(json.dumps(asdict(row), separators=(",", ":")) + "\n" for row in rows)

        with path.open("a") as file:
            file.write(payload)

def _float(value) -> float | None:
    return None if value is None else float(value)