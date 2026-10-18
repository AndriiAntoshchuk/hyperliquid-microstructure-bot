import argparse
import json
from pathlib import Path

from hlbot.data.hyperliquid_ws_collector import build_record
from hlbot.data.hyperliquid_ws_paths import output_path

START_MS = 1_780_000_000_000


def demo_mid(second: int) -> float:
    if second < 45:
        return 100.0
    if second <= 52:
        return 100.0 - 0.28 * (second - 44)
    if second <= 72:
        return 97.76 + 0.112 * (second - 52)
    return 100.0


def generate(data_dir: str | Path) -> tuple[Path, Path]:
    data_dir = Path(data_dir)
    grouped = {"l2Book": [], "trades": []}
    for i in range(120):
        ms = START_MS + i * 1000
        ns = (ms + 5) * 1_000_000
        mid = demo_mid(i)
        levels = [
            [{"px": f"{mid - 0.05 - j * 0.05:.4f}", "sz": "50"} for j in range(5)],
            [{"px": f"{mid + 0.05 + j * 0.05:.4f}", "sz": "50"} for j in range(5)],
        ]
        for channel, payload in (
            ("l2Book", {"coin": "DEMO", "time": ms, "levels": levels}),
            ("trades", [{"coin": "DEMO", "time": ms, "tid": i + 1,
                         "px": f"{mid:.4f}", "sz": "1", "side": "B"}]),
        ):
            grouped[channel].append(json.dumps(
                build_record(channel, payload, "DEMO", "synthetic_fixture", i + 1, ns),
                separators=(",", ":"),
            ))

    paths = []
    for channel, lines in grouped.items():
        path = output_path(data_dir, "DEMO", channel, (START_MS + 5) * 1_000_000)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/sample")
    args = parser.parse_args()
    for path in generate(args.output):
        print(path)


if __name__ == "__main__":
    main()
