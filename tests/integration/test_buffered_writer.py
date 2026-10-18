import asyncio
import json
import time

import pytest

from hlbot.data import buffered_writer
from hlbot.data.buffered_writer import BufferedJSONLWriter
from hlbot.data.hyperliquid_ws_collector import write_record
from hlbot.data.hyperliquid_ws_paths import output_path


def record(index, *, coin="PONS", ns=1_780_000_000_000_000_000):
    return {"coin": coin, "channel": "l2Book", "local_receive_ns": ns,
            "data": {"index": index}}


@pytest.mark.asyncio
async def test_batched_output_matches_previous_writer_and_rotates(tmp_path):
    records = [record(i, coin="PONS" if i % 2 == 0 else "PURR") for i in range(31)]
    records.append(record(99, ns=1_780_100_000_000_000_000))
    old_dir, new_dir = tmp_path / "old", tmp_path / "new"
    for item in records:
        write_record(old_dir, item)

    async with BufferedJSONLWriter(new_dir, max_queue=3, batch_size=7, flush_interval=0.01) as writer:
        for item in records:
            await writer.write(item)
        assert writer.queued <= 3

    for old_file in old_dir.rglob("*.jsonl"):
        assert (new_dir / old_file.relative_to(old_dir)).read_bytes() == old_file.read_bytes()
    assert writer.metrics.records_written == len(records)
    assert writer.metrics.bytes_written == sum(len(json.dumps(item, separators=(",", ":")).encode()) + 1 for item in records)
    assert writer.metrics.batches_written >= 2
    assert writer.metrics.queue_peak <= 3


@pytest.mark.asyncio
async def test_flush_on_shutdown_before_batch_full(tmp_path):
    async with BufferedJSONLWriter(tmp_path, batch_size=1000, flush_interval=3600) as writer:
        await writer.write(record(1))
    path = output_path(tmp_path, "PONS", "l2Book", record(1)["local_receive_ns"])
    assert len(path.read_text().splitlines()) == 1
    assert writer.metrics.records_written == 1


@pytest.mark.asyncio
async def test_backpressure_and_error_propagation(tmp_path, monkeypatch):
    original = buffered_writer._write_batch

    def slow_write(path, records):
        time.sleep(0.02)
        return original(path, records)

    monkeypatch.setattr(buffered_writer, "_write_batch", slow_write)
    async with BufferedJSONLWriter(tmp_path / "slow", max_queue=1, batch_size=1) as writer:
        for i in range(10):
            await writer.write(record(i))
    assert writer.metrics.enqueue_wait_seconds >= 0.01
    assert writer.metrics.records_written == 10

    def broken_write(path, records):
        raise OSError("disk unavailable")

    monkeypatch.setattr(buffered_writer, "_write_batch", broken_write)
    failing = BufferedJSONLWriter(tmp_path / "failed", max_queue=1, batch_size=1)
    await failing.start()
    await failing.write(record(1))
    with pytest.raises(OSError, match="disk unavailable"):
        await asyncio.wait_for(failing.close(), 2)
