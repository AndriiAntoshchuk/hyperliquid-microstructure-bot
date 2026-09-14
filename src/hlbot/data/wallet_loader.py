import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from hlbot.models.wallet_fill import WalletFill

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"
MAX_FILLS_PER_REQUEST = 2000
MAX_AVAILABLE_FILLS = 10000

class HyperliquidWalletLoader:
    def __init__(self, data_dir: str | Path = "data", timeout: int = 30):
        self.data_dir = Path(data_dir)
        self.timeout = timeout

    def download(self, wallet: str, start_time_ms: int, end_time_ms: int | None = None) -> tuple[list[WalletFill], bool]:
        self._validate_wallet(wallet)

        raw_fills = self._download_raw(wallet, start_time_ms, end_time_ms)
        fills = self._deduplicate(self._normalize(wallet, raw_fills))
        batch_name = self._batch_name(wallet, start_time_ms, end_time_ms)

        self._save_raw(batch_name, raw_fills)
        self._save_processed(batch_name, fills)

        history_may_be_incomplete = len(raw_fills) >= MAX_AVAILABLE_FILLS
        return fills, history_may_be_incomplete

    def load_saved(self, wallet: str) -> list[WalletFill]:
        self._validate_wallet(wallet)

        directory = self.data_dir / "processed" / "wallets"
        if not directory.exists(): return []

        wallet = wallet.lower()
        paths = sorted(directory.glob(f"{wallet}_*_fills.jsonl"))

        legacy_path = directory / f"{wallet}_fills.jsonl"
        if legacy_path.exists(): paths.insert(0, legacy_path)

        fills = []

        for path in paths:
            with path.open() as file:
                for line in file:
                    if line.strip(): fills.append(WalletFill(**json.loads(line)))

        return self._deduplicate(fills)

    def _download_raw(self, wallet: str, start_time_ms: int, end_time_ms: int | None) -> list[dict[str, Any]]:
        fills = []
        current_start = start_time_ms

        while len(fills) < MAX_AVAILABLE_FILLS:
            payload = {
                "type": "userFillsByTime",
                "user": wallet,
                "startTime": current_start,
                "aggregateByTime": False
            }

            if end_time_ms is not None: payload["endTime"] = end_time_ms

            response = requests.post(HYPERLIQUID_INFO_URL, json=payload, timeout=self.timeout)
            response.raise_for_status()
            page = response.json()

            if not isinstance(page, list): raise ValueError("Unexpected Hyperliquid API response")
            if not page: break

            fills.extend(page)

            if len(page) < MAX_FILLS_PER_REQUEST: break

            last_time = max(int(fill["time"]) for fill in page)
            if last_time < current_start: raise ValueError("Hyperliquid pagination moved backwards")

            current_start = last_time + 1

            if end_time_ms is not None and current_start > end_time_ms: break

        return fills[:MAX_AVAILABLE_FILLS]

    def _normalize(self, wallet: str, raw_fills: list[dict[str, Any]]) -> list[WalletFill]:
        return [self._normalize_fill(wallet, fill) for fill in raw_fills]

    @staticmethod
    def _normalize_fill(wallet: str, fill: dict[str, Any]) -> WalletFill:
        timestamp_ms = int(fill["time"])
        coin = str(fill["coin"])
        tid = str(fill["tid"])

        if fill["side"] not in {"B", "A"}: raise ValueError(f"Unknown Hyperliquid side: {fill['side']}")

        return WalletFill(
            wallet=wallet.lower(),
            coin=coin,
            timestamp=timestamp_ms / 1000,
            price=float(fill["px"]),
            quantity=float(fill["sz"]),
            side="buy" if fill["side"] == "B" else "sell",
            trade_id=f"{timestamp_ms}:{coin}:{tid}",
            direction=str(fill["dir"]),
            order_id=int(fill["oid"]),
            closed_pnl=float(fill["closedPnl"]),
            crossed=bool(fill["crossed"]),
            fee=float(fill.get("fee", 0)),
            fee_token=str(fill.get("feeToken", "")),
            transaction_hash=str(fill["hash"]),
            start_position=float(fill["startPosition"]) if fill.get("startPosition") is not None else None,
            client_order_id=str(fill["cloid"]) if fill.get("cloid") is not None else None,
            twap_id=int(fill["twapId"]) if fill.get("twapId") is not None else None
        )

    @staticmethod
    def _deduplicate(fills: list[WalletFill]) -> list[WalletFill]:
        seen = set()
        unique = []

        for fill in fills:
            if fill.trade_id in seen: continue
            seen.add(fill.trade_id)
            unique.append(fill)

        return sorted(unique, key=lambda fill: fill.timestamp)

    @staticmethod
    def _batch_name(wallet: str, start_time_ms: int, end_time_ms: int | None) -> str:
        start = datetime.fromtimestamp(start_time_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
        end = datetime.fromtimestamp(end_time_ms / 1000, timezone.utc).strftime("%Y-%m-%d") if end_time_ms is not None else "open"
        downloaded = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{wallet.lower()}_{start}_{end}_{downloaded}"

    def _save_raw(self, batch_name: str, fills: list[dict[str, Any]]) -> None:
        directory = self.data_dir / "raw" / "wallets"
        directory.mkdir(parents=True, exist_ok=True)

        with open(directory / f"{batch_name}_raw.json", "w") as file:
            json.dump(fills, file, indent=2)

    def _save_processed(self, batch_name: str, fills: list[WalletFill]) -> None:
        directory = self.data_dir / "processed" / "wallets"
        directory.mkdir(parents=True, exist_ok=True)

        with open(directory / f"{batch_name}_fills.jsonl", "w") as file:
            for fill in fills: file.write(json.dumps(asdict(fill)) + "\n")

    @staticmethod
    def _validate_wallet(wallet: str) -> None:
        if len(wallet) != 42 or not wallet.startswith("0x"): raise ValueError("wallet must be a 42-character Hyperliquid address")

        try:
            int(wallet[2:], 16)
        except ValueError:
            raise ValueError("wallet contains invalid hexadecimal characters")