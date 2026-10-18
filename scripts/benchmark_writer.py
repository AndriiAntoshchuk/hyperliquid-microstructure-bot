import argparse
import asyncio
import json
import platform
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from hlbot.data.buffered_writer import BufferedJSONLWriter
from hlbot.data.hyperliquid_ws_collector import write_record
from hlbot.data.hyperliquid_ws_paths import output_path


def sample_records(count: int) -> list[dict]:
    return [
        {"coin": "DEMO", "channel": "trades", "local_receive_ns": 1_780_000_000_000_000_000 + i * 1_000_000,
         "data": [{"px": "100.1", "sz": "1", "tid": i}]}
        for i in range(count)
    ]


async def benchmark(count: int, max_queue: int, batch_size: int) -> dict:
    if count < 1:
        raise ValueError("count must be positive")
    records = sample_records(count)
    with tempfile.TemporaryDirectory(prefix="hlbot_writer_benchmark_") as root:
        root = Path(root)
        sync_dir, buffered_dir = root / "sync", root / "buffered"
        start = time.perf_counter()
        for record in records:
            write_record(sync_dir, record)
        sync_seconds = time.perf_counter() - start

        start = time.perf_counter()
        async with BufferedJSONLWriter(buffered_dir, max_queue=max_queue, batch_size=batch_size) as writer:
            for record in records:
                await writer.write(record)
        buffered_seconds = time.perf_counter() - start
        expected_path = output_path(sync_dir, "DEMO", "trades", records[0]["local_receive_ns"])
        actual_path = output_path(buffered_dir, "DEMO", "trades", records[0]["local_receive_ns"])
        if expected_path.read_bytes() != actual_path.read_bytes():
            raise RuntimeError("baseline and buffered output do not match")

    return {
        "description": "sync per-record append vs bounded async batched append",
        "records": count,
        "python": platform.python_version(),
        "system": platform.platform(),
        "max_queue": max_queue,
        "batch_size": batch_size,
        "sync_seconds": sync_seconds,
        "sync_records_per_second": count / sync_seconds,
        "buffered_seconds": buffered_seconds,
        "buffered_records_per_second": count / buffered_seconds,
        "speedup": sync_seconds / buffered_seconds,
        "buffered_metrics": asdict(writer.metrics),
        "output_verified_equal": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=3000)
    parser.add_argument("--queue-size", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--output", default="reports/writer_benchmark.json")
    args = parser.parse_args()
    report = asyncio.run(benchmark(args.records, args.queue_size, args.batch_size))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
