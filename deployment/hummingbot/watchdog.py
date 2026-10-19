from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def latest_snapshot(directory: Path, market: str) -> Path | None:
    pattern = f"hyperliquid_perpetual_{market}-USD_order_book_snapshots_*.txt"
    files = (path for path in directory.glob(pattern) if path.is_file())
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def check_health(container: str, data_dir: Path, markets: tuple[str, ...], max_age: float, now: float,) -> tuple[bool, list[str]]:
    messages: list[str] = []
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        running = result.returncode == 0 and result.stdout.strip() == "true"
    except (OSError, subprocess.TimeoutExpired) as exc:
        running = False
        messages.append(f"docker inspect failed: {exc}")

    if not running:
        messages.append(f"container {container}: not running")
    markets_ok = True
    for market in markets:
        path = latest_snapshot(data_dir, market)
        if path is None:
            markets_ok = False
            messages.append(f"{market}: missing order-book snapshots")
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            markets_ok = False
            messages.append(f"{market}: cannot stat snapshot: {exc}")
            continue
        age = max(0.0, now - stat.st_mtime)
        if age > max_age or stat.st_size == 0:
            markets_ok = False
            messages.append(f"{market}: stale/empty (age={age:.1f}s size={stat.st_size})")
        else:
            messages.append(f"{market}: healthy (age={age:.1f}s)")

    healthy = running and markets_ok
    return healthy, messages


def main() -> int:
    container = os.environ.get("HB_CONTAINER", "hummingbot")
    data_dir = Path(os.environ.get("HB_DATA_DIR", "/srv/hummingbot/data"))
    markets = tuple(os.environ.get("HB_MARKETS", "PONS CASHCAT PURR LIT").split())
    max_age = float(os.environ.get("HB_MAX_AGE_SECONDS", "300"))
    cooldown = float(os.environ.get("HB_RESTART_COOLDOWN_SECONDS", "600"))
    state_dir = Path(os.environ.get("HB_STATE_DIR", "/var/lib/hlbot"))
    dry_run = os.environ.get("HB_DRY_RUN", "1") != "0"
    if not markets or max_age <= 0 or cooldown < 0:
        print("Invalid watchdog configuration", file=sys.stderr)
        return 2

    now = time.time()
    healthy, messages = check_health(container, data_dir, markets, max_age, now)
    for message in messages:
        print(message, flush=True)
    if healthy:
        print("Collector healthy", flush=True)
        return 0

    if dry_run:
        print(f"DRY RUN: would restart container {container}", flush=True)
        return 1

    state_file = state_dir / "last_restart"
    try:
        last_restart = float(state_file.read_text().strip()) if state_file.exists() else 0.0
        if now - last_restart < cooldown:
            print("Restart suppressed by cooldown", flush=True)
            return 1
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(f"{now:.3f}\n")
        result = subprocess.run(
            ["docker", "restart", container],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Restart failed: {exc}", file=sys.stderr)
        return 2
    if result.returncode:
        print(f"Docker restart failed: {result.stderr.strip()}", file=sys.stderr)
        return 2
    print(f"Restart requested for {container}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
